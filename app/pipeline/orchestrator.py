import shutil
import threading
import time
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any
import httpx
from sqlmodel import Session

from app.config import settings
from app.database import engine
from app.models.job import Job, JobStatus, DirectorPlan, EditSegment, VisualCue
from app.services.transcriber import get_transcriber
from app.services.semantic_director import SemanticDirector
from app.services.broll_manager import LocalBrollManager
from app.services.svg_generator import ProceduralSvgGenerator
from app.services.subtitle_generator import SubtitleGenerator
from app.services.ffmpeg_renderer import FFmpegRenderer

logger = logging.getLogger(__name__)

# FFmpeg + Whisper saturate CPU/GPU; running N jobs in parallel only makes all of them slow.
_render_slots = threading.BoundedSemaphore(max(1, settings.MAX_CONCURRENT_JOBS))


class JobCancelled(Exception):
    """Raised between stages when the user cancelled the job."""


class VideoPipelineOrchestrator:
    """100% Local Autonomous Video Production Pipeline Orchestrator."""

    def __init__(self):
        self.transcriber = get_transcriber()  # model loaded once per process
        self.director = SemanticDirector()
        self.broll_manager = LocalBrollManager()
        self.svg_generator = ProceduralSvgGenerator()
        self.subtitle_generator = SubtitleGenerator()
        self.renderer = FFmpegRenderer()

    def run_pipeline(
        self,
        job_id: str,
        input_video_path: str,
        output_video_path: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Job:
        """Executes full autonomous video creation workflow (serialised by ``_render_slots``)."""
        with _render_slots:
            return self._run_pipeline(job_id, input_video_path, output_video_path, options)

    def _run_pipeline(
        self,
        job_id: str,
        input_video_path: str,
        output_video_path: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Job:
        options = options or {}
        start_time = time.time()
        in_path = Path(input_video_path).resolve()

        if not in_path.exists():
            raise FileNotFoundError(f"Input video file not found: {in_path}")

        if not output_video_path:
            out_filename = f"final_{in_path.stem}_{int(time.time())}.mp4"
            out_path = settings.OUTPUTS_DIR / out_filename
        else:
            out_path = Path(output_video_path).resolve()

        out_path.parent.mkdir(parents=True, exist_ok=True)

        with Session(engine) as session:
            job = session.get(Job, job_id)
            if not job:
                job = Job(
                    id=job_id,
                    input_path=str(in_path),
                    output_path=str(out_path),
                    status=JobStatus.QUEUED,
                    current_step="Starting pipeline"
                )
                session.add(job)
                session.commit()
                session.refresh(job)

            if job.status == JobStatus.CANCELLED:
                logger.info(f"[{job.id}] Cancelled before start; skipping.")
                return job

            try:
                # ----------------------------------------------------
                # STEP 1: TRANSCRIPTION (faster-whisper)
                # ----------------------------------------------------
                self._update_job(session, job, JobStatus.TRANSCRIBING, 15.0, "Transcribing with faster-whisper")
                logger.info(f"[{job.id}] Step 1: Transcribing {in_path}...")
                
                transcript_data = self.transcriber.transcribe(
                    media_path=str(in_path),
                    word_timestamps=True
                )
                job.transcript_json = json.dumps(transcript_data)
                session.add(job)
                session.commit()

                # ----------------------------------------------------
                # STEP 2: SEMANTIC DIRECTOR (Ollama Take Pruning)
                # ----------------------------------------------------
                self._update_job(session, job, JobStatus.DIRECTING, 35.0, "Analyzing takes with Ollama LLM")
                logger.info(f"[{job.id}] Step 2: Semantic Director analyzing takes & script...")

                plan: DirectorPlan = self.director.direct(transcript_data)
                
                # Safeguard: ensure at least one segment is kept
                if not any(s.keep for s in plan.edit_decision_list):
                    dur = transcript_data.get("duration", 5.0) or 5.0
                    plan.edit_decision_list = [
                        EditSegment(start=0.0, end=dur, keep=True, reason="Full length retention", text="")
                    ]

                job.edl_json = json.dumps([seg.model_dump() for seg in plan.edit_decision_list])
                job.director_summary_json = plan.model_dump_json()
                session.add(job)
                session.commit()

                # ----------------------------------------------------
                # STEP 3: ASSET SELECTION & PROCEDURAL GENERATION
                # ----------------------------------------------------
                self._update_job(session, job, JobStatus.SELECTING_ASSETS, 50.0, "Matching B-roll & generating SVG cards")
                logger.info(f"[{job.id}] Step 3: Preparing visual assets...")

                enable_broll = options.get("enable_broll", True)
                enable_svg = options.get("enable_svg_cards", True)

                for cue in plan.visual_cues:
                    if cue.asset_type == "broll" and enable_broll:
                        asset = self.broll_manager.select_broll_for_cue(cue.query_or_topic, session)
                        if asset:
                            cue.asset_path = asset.file_path
                    elif cue.asset_type == "svg_card" and enable_svg:
                        svg_path = self.svg_generator.generate_card(
                            card_type=cue.card_type or "stat",
                            title=cue.card_title or "HIGHLIGHT",
                            content=cue.card_content or "Key concept",
                            badge="INSIGHT"
                        )
                        cue.asset_path = svg_path

                # ----------------------------------------------------
                # STEP 4: VIDEO & AUDIO RENDERING (FFmpeg)
                # ----------------------------------------------------
                self._update_job(session, job, JobStatus.RENDERING, 65.0, "Splicing jumpcuts with 20ms audio crossfade")
                logger.info(f"[{job.id}] Step 4: Splicing jumpcuts...")

                # 4.1 Assemble kept takes
                jumpcuts_out = str(settings.CACHE_DIR / f"{job.id}_jumpcuts.mp4")
                self.renderer.assemble_jumpcuts_with_crossfade(
                    input_video=str(in_path),
                    edl=plan.edit_decision_list,
                    output_path=jumpcuts_out
                )

                # 4.2 Composite visual overlays (B-roll & SVG cards)
                current_stage_video = jumpcuts_out
                valid_overlays = [c for c in plan.visual_cues if c.asset_path]
                if valid_overlays:
                    self._update_job(session, job, JobStatus.RENDERING, 75.0, "Compositing B-roll and graphics")
                    overlays_out = str(settings.CACHE_DIR / f"{job.id}_overlays.mp4")
                    current_stage_video = self.renderer.apply_visual_overlays(
                        base_video=current_stage_video,
                        visual_cues=valid_overlays,
                        output_path=overlays_out
                    )

                # 4.3 Background Music & Ducking (-22 dB)
                enable_ducking = options.get("enable_music_ducking", True)
                music_path = options.get("music_track_path") or self._get_default_music_track()
                if enable_ducking and music_path and Path(music_path).exists():
                    self._update_job(session, job, JobStatus.RENDERING, 85.0, "Applying -22dB ambient audio ducking")
                    ducked_out = str(settings.CACHE_DIR / f"{job.id}_ducked.mp4")
                    current_stage_video = self.renderer.apply_audio_ducking(
                        video_path=current_stage_video,
                        music_path=music_path,
                        output_path=ducked_out
                    )

                # 4.4 Kinetic ASS Subtitles with Word Highlighting
                enable_subs = options.get("enable_subtitles", True)
                if enable_subs:
                    sync_mode = options.get("subtitle_sync_mode", "word_by_word")
                    self._update_job(session, job, JobStatus.RENDERING, 92.0, f"Generating & burning kinetic subtitles ({sync_mode})")
                    ass_path = self.subtitle_generator.generate_kinetic_ass(
                        transcript_segments=transcript_data.get("segments", []),
                        edl=plan.edit_decision_list,
                        output_filename=f"{job.id}_subtitles.ass",
                        sync_mode=sync_mode
                    )
                    final_render = self.renderer.burn_subtitles(
                        video_path=current_stage_video,
                        ass_path=ass_path,
                        output_path=str(out_path)
                    )
                else:
                    shutil.copyfile(current_stage_video, str(out_path))

                # ----------------------------------------------------
                # STEP 5: FINISH & INTEROPERABILITY (n8n Webhook)
                # ----------------------------------------------------
                total_duration = round(time.time() - start_time, 2)
                job.output_path = str(out_path)
                job.execution_time_seconds = total_duration
                self._update_job(session, job, JobStatus.COMPLETED, 100.0, "Production complete")
                logger.info(f"[{job.id}] Pipeline successfully completed in {total_duration}s -> {out_path}")

                # Trigger local n8n webhook if requested
                webhook_url = job.n8n_webhook_url or options.get("n8n_webhook_url") or settings.N8N_DEFAULT_WEBHOOK_URL
                if webhook_url:
                    self._dispatch_n8n_webhook(webhook_url, job, plan)

                return job

            except JobCancelled:
                logger.info(f"[{job.id}] Pipeline stopped: cancelled by user.")
                return job
            except Exception as e:
                logger.exception(f"[{job.id}] Pipeline failed: {e}")
                job.status = JobStatus.FAILED
                job.error_message = str(e)
                job.current_step = f"Failed: {str(e)[:100]}"
                job.updated_at = datetime.now(timezone.utc)
                session.add(job)
                session.commit()
                raise

    def _update_job(
        self, session: Session, job: Job, status: JobStatus, progress: float, step: str
    ) -> None:
        session.refresh(job)  # pick up a cancel issued from the API in another session
        if job.status == JobStatus.CANCELLED:
            raise JobCancelled(job.id)
        job.status = status
        job.progress = progress
        job.current_step = step
        job.updated_at = datetime.now(timezone.utc)
        session.add(job)
        session.commit()
        session.refresh(job)

    def _get_default_music_track(self) -> Optional[str]:
        """Looks for an available ambient music track in storage/audio_library/ or creates a subtle tone."""
        audio_dir = settings.AUDIO_DIR
        for f in audio_dir.glob("*.mp3"):
            return str(f.resolve())
        for f in audio_dir.glob("*.wav"):
            return str(f.resolve())
        return None

    def _dispatch_n8n_webhook(self, webhook_url: str, job: Job, plan: DirectorPlan) -> None:
        """Sends job completion notification payload to local n8n instance."""
        payload = {
            "event": "video.rendered",
            "job_id": job.id,
            "status": job.status.value,
            "input_path": job.input_path,
            "output_path": job.output_path,
            "execution_time_seconds": job.execution_time_seconds,
            "title": plan.title,
            "hook": plan.hook,
            "summary": plan.summary,
            "pruned_takes_count": plan.removed_takes_count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        logger.info(f"Notifying n8n webhook at: {webhook_url}")
        try:
            with httpx.Client(timeout=4.0) as client:
                res = client.post(webhook_url, json=payload)
                logger.info(f"n8n webhook response: HTTP {res.status_code}")
        except Exception as e:
            logger.warning(f"Could not reach n8n webhook at {webhook_url}: {e}")
