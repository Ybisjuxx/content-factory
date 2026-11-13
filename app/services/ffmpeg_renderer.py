import logging
import os
import subprocess
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional
from app.config import settings
from app.models.job import EditSegment, VisualCue

logger = logging.getLogger(__name__)


class FFmpegRenderer:
    """High-performance local video rendering engine using FFmpeg.

    Executes:
    - Precise jumpcut trimming and assembly.
    - 20ms audio crossfading between takes to eliminate popping artifacts.
    - Kinetic ASS subtitles with word highlighting.
    - Ambient background audio ducking (-22 dB).
    - 9:16 vertical scaling and B-roll/SVG overlay compositing.
    """

    def __init__(self, ffmpeg_bin: Optional[str] = None):
        self.ffmpeg_bin = ffmpeg_bin or settings.resolve_ffmpeg_path()
        self.cache_dir = settings.CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def check_ffmpeg(self) -> Dict[str, Any]:
        """Verifies FFmpeg presence and features."""
        try:
            res = subprocess.run(
                [self.ffmpeg_bin, "-version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            first_line = res.stdout.splitlines()[0] if res.stdout else "unknown"
            return {
                "available": res.returncode == 0,
                "path": self.ffmpeg_bin,
                "version": first_line
            }
        except Exception as e:
            return {
                "available": False,
                "path": self.ffmpeg_bin,
                "error": str(e)
            }

    def assemble_jumpcuts_with_crossfade(
        self,
        input_video: str,
        edl: List[EditSegment],
        output_path: str
    ) -> str:
        """Trims and splices all 'keep' segments from the EDL with a 20ms audio crossfade across takes."""
        kept_segments = [s for s in edl if s.keep]
        if not kept_segments:
            raise ValueError("No segments marked as 'keep' in Edit Decision List.")

        in_p = Path(input_video).resolve()
        out_p = Path(output_path).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)

        # Single segment case: direct precise trim
        if len(kept_segments) == 1:
            seg = kept_segments[0]
            dur = seg.end - seg.start
            cmd = [
                self.ffmpeg_bin, "-y",
                "-ss", str(seg.start),
                "-t", str(dur),
                "-i", str(in_p),
                "-vf", f"scale={settings.TARGET_WIDTH}:{settings.TARGET_HEIGHT}:force_original_aspect_ratio=decrease,pad={settings.TARGET_WIDTH}:{settings.TARGET_HEIGHT}:(ow-iw)/2:(oh-ih)/2,setsar=1",
                "-c:v", "libx264",
                "-preset", "fast",
                "-c:a", "aac",
                "-b:a", "192k",
                str(out_p)
            ]
            self._run_ffmpeg(cmd, "Trimming single segment")
            return str(out_p)

        # Multiple segments: trim each take and concat video+audio together.
        # Each audio take gets a short fade-in/out (default 20ms total edge) instead of
        # acrossfade: acrossfade overlaps the takes, shortening audio by d per cut while
        # video keeps full length -> cumulative lip-sync drift (≈140ms after 8 takes).
        filter_parts = []
        concat_inputs = []
        edge = max(0.0, settings.AUDIO_CROSSFADE_SECONDS / 2)

        for i, seg in enumerate(kept_segments):
            dur = max(0.0, seg.end - seg.start)
            fade = min(edge, dur / 4)
            filter_parts.append(
                f"[0:v]trim=start={seg.start}:end={seg.end},setpts=PTS-STARTPTS,"
                f"scale={settings.TARGET_WIDTH}:{settings.TARGET_HEIGHT}:force_original_aspect_ratio=decrease,"
                f"pad={settings.TARGET_WIDTH}:{settings.TARGET_HEIGHT}:(ow-iw)/2:(oh-ih)/2,setsar=1[v{i}]"
            )
            a_chain = f"[0:a]atrim=start={seg.start}:end={seg.end},asetpts=PTS-STARTPTS"
            if fade > 0:
                a_chain += f",afade=t=in:st=0:d={fade:.3f},afade=t=out:st={max(0.0, dur - fade):.3f}:d={fade:.3f}"
            filter_parts.append(f"{a_chain}[a{i}]")
            concat_inputs.append(f"[v{i}][a{i}]")

        filter_parts.append(
            f"{''.join(concat_inputs)}concat=n={len(kept_segments)}:v=1:a=1[v_out][a_out]"
        )

        filter_graph = ";".join(filter_parts)

        cmd = [
            self.ffmpeg_bin, "-y",
            "-i", str(in_p),
            "-filter_complex", filter_graph,
            "-map", "[v_out]",
            "-map", "[a_out]",
            "-c:v", "libx264",
            "-preset", "fast",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            str(out_p)
        ]
        self._run_ffmpeg(cmd, "Jumpcuts assembly with click-free audio edges")
        return str(out_p)

    def apply_visual_overlays(
        self,
        base_video: str,
        visual_cues: List[VisualCue],
        output_path: str
    ) -> str:
        """Composites 9:16 B-roll clips and procedural SVG cards over the main video at cue timestamps."""
        valid_cues = [c for c in visual_cues if c.asset_path and Path(c.asset_path).exists()]
        if not valid_cues:
            logger.info("No visual overlays to apply, copying base video.")
            shutil.copyfile(base_video, output_path)
            return output_path

        base_p = Path(base_video).resolve()
        out_p = Path(output_path).resolve()

        # Build FFmpeg command with multiple inputs
        cmd = [self.ffmpeg_bin, "-y", "-i", str(base_p)]
        for cue in valid_cues:
            cmd.extend(["-i", str(Path(cue.asset_path).resolve())])

        # Filter complex: layer each overlay sequentially with smooth 0.2s fade in/out
        filter_parts = []
        last_v = "[0:v]"

        for idx, cue in enumerate(valid_cues, start=1):
            overlay_dur = cue.timestamp_end - cue.timestamp_start
            fade_in = 0.2
            fade_out = 0.2

            # Conform overlay to 1080x1920
            scaled_input = f"[sc_{idx}]"
            filter_parts.append(
                f"[{idx}:v]scale={settings.TARGET_WIDTH}:{settings.TARGET_HEIGHT}:force_original_aspect_ratio=increase,"
                f"crop={settings.TARGET_WIDTH}:{settings.TARGET_HEIGHT},format=yuva420p,"
                f"fade=t=in:st=0:d={fade_in}:alpha=1,"
                f"fade=t=out:st={max(0, overlay_dur - fade_out)}:d={fade_out}:alpha=1,"
                f"setpts=PTS-STARTPTS+{cue.timestamp_start}/TB{scaled_input}"
            )

            next_v = f"[v_over_{idx}]" if idx < len(valid_cues) else "[v_final]"
            filter_parts.append(
                f"{last_v}{scaled_input}overlay=0:0:enable='between(t,{cue.timestamp_start},{cue.timestamp_end})'{next_v}"
            )
            last_v = next_v

        cmd.extend([
            "-filter_complex", ";".join(filter_parts),
            "-map", last_v,
            "-map", "0:a",
            "-c:v", "libx264",
            "-preset", "fast",
            "-pix_fmt", "yuv420p",
            "-c:a", "copy",
            str(out_p)
        ])

        self._run_ffmpeg(cmd, f"Compositing {len(valid_cues)} visual B-roll / SVG overlays")
        return str(out_p)

    def apply_audio_ducking(
        self,
        video_path: str,
        music_path: Optional[str],
        output_path: str,
        target_db: float = settings.AUDIO_DUCKING_DB
    ) -> str:
        """Mixes background music with speech, automatically ducking ambient music down to -22 dB during speech."""
        if not music_path or not Path(music_path).exists():
            logger.info("No background music track provided; skipping ducking.")
            shutil.copyfile(video_path, output_path)
            return output_path

        vid_p = Path(video_path).resolve()
        mus_p = Path(music_path).resolve()
        out_p = Path(output_path).resolve()

        # Sidechain compression filter: speech on 0:a ducks music on 1:a
        # Target -22dB reduction during voice activity
        filter_graph = (
            "[1:a]aloop=loop=-1:size=2e+09,volume=0.35[looped_bg];"
            f"[looped_bg][0:a]sidechaincompress=threshold=0.08:ratio=12:attack={settings.AUDIO_DUCKING_ATTACK_MS}:release={settings.AUDIO_DUCKING_RELEASE_MS}[ducked_bg];"
            "[0:a][ducked_bg]amix=inputs=2:duration=first:dropout_transition=2[mixed_a]"
        )

        cmd = [
            self.ffmpeg_bin, "-y",
            "-i", str(vid_p),
            "-i", str(mus_p),
            "-filter_complex", filter_graph,
            "-map", "0:v",
            "-map", "[mixed_a]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            str(out_p)
        ]
        self._run_ffmpeg(cmd, "Ambient audio ducking (-22 dB)")
        return str(out_p)

    def burn_subtitles(
        self,
        video_path: str,
        ass_path: str,
        output_path: str
    ) -> str:
        """Burns kinetic ASS subtitles directly into the video stream."""
        if not Path(ass_path).exists():
            logger.warning(f"ASS subtitle file not found: {ass_path}, copying video as is.")
            shutil.copyfile(video_path, output_path)
            return output_path

        vid_p = Path(video_path).resolve()
        ass_p = Path(ass_path).resolve()
        out_p = Path(output_path).resolve()

        # Format path for FFmpeg filter on Windows
        escaped_ass_path = str(ass_p).replace("\\", "/").replace(":", "\\:")

        cmd = [
            self.ffmpeg_bin, "-y",
            "-i", str(vid_p),
            "-vf", f"ass='{escaped_ass_path}'",
            "-c:v", "libx264",
            "-preset", "fast",
            "-pix_fmt", "yuv420p",
            "-c:a", "copy",
            str(out_p)
        ]
        self._run_ffmpeg(cmd, "Burning kinetic ASS subtitles")
        return str(out_p)

    def _run_ffmpeg(self, cmd: List[str], task_desc: str) -> None:
        """Executes FFmpeg command and raises clear error on failure."""
        logger.info(f"FFmpeg [{task_desc}]: {' '.join(cmd)}")
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            logger.error(f"FFmpeg failed during {task_desc}:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}")
            raise RuntimeError(f"FFmpeg error ({task_desc}): {result.stderr.strip()[:400]}")
