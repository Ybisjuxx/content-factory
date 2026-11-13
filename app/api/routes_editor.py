import logging
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Dict, Any, List, Literal, Optional
from fastapi import APIRouter, File, UploadFile, HTTPException, Form
from pydantic import BaseModel, Field

from app.config import settings
from app.services.transcriber import get_transcriber
from app.security import resolve_media_path, safe_filename, sanitize_hex_color
from app.api.uploads import save_upload, VIDEO_EXTENSIONS
from app.services.subtitle_generator import SubtitleGenerator
from app.services.motion_graphics import MotionGraphicsService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/editor", tags=["OpenCut Studio Pro Editor API"])

transcriber = get_transcriber()
subtitle_gen = SubtitleGenerator()
motion_service = MotionGraphicsService()


class TranscribeRequest(BaseModel):
    video_path: str = Field(..., description="Local path or filename of video to transcribe")
    language: Optional[str] = Field(None, description="Language code e.g. 'es', 'en' or None for auto")
    sync_mode: Optional[str] = Field("word_by_word", description="Sync mode: 'word_by_word', 'cumulative', 'karaoke'")


class SubtitleExportStyle(BaseModel):
    font_name: str = "Impact"
    font_size: int = 24
    highlight_color: str = "#ffff00"
    primary_color: str = "#ffffff"
    margin_v: int = 420
    sync_mode: str = "word_by_word"
    max_words_per_group: int = 4


class MotionOverlayExportConfig(BaseModel):
    preset_id: str = "lower_third_glass"
    title: Optional[str] = "ALEX RIVERA"
    subtitle: Optional[str] = "Especialista en IA"
    badge: Optional[str] = "CREADOR"
    accent_color: str = "#38BDF8"
    metric: Optional[str] = "+350%"
    explanation: Optional[str] = "Crecimiento de Retención"
    headline: Optional[str] = "NO COMETAS ESTE ERROR"
    subheadline: Optional[str] = "Mira esto antes de subir tu próximo video"
    cta_text: Optional[str] = "★ Sígueme para más trucos"
    subtext: Optional[str] = "Guarda este video"
    handle: Optional[str] = "@alex_ai"
    platform: Optional[str] = "TikTok / Reels"
    quote: Optional[str] = "La clave no es la suerte sino la retención"
    author: Optional[str] = "Alex Rivera"
    number_val: Optional[str] = "+250K"
    label: Optional[str] = "Reproducciones Orgánicas"
    sublabel: Optional[str] = "Enlace en mi perfil"
    warning_title: Optional[str] = "¡DETENTE AQUÍ!"
    warning_desc: Optional[str] = "Error que destruye tu retención"
    start_time: float = 1.0
    duration: float = 5.0


class ExportEditorRequest(BaseModel):
    video_path: str
    aspect_ratio: Literal["9:16", "16:9", "1:1", "original"] = "9:16"
    speed: float = Field(1.0, ge=0.25, le=4.0)
    brightness: float = Field(1.0, ge=0.0, le=2.0)
    contrast: float = Field(1.0, ge=0.0, le=3.0)
    saturation: float = Field(1.0, ge=0.0, le=3.0)
    include_subtitles: bool = True
    subtitle_style: Optional[SubtitleExportStyle] = None
    transcript_segments: Optional[List[Dict[str, Any]]] = None
    motion_overlay: Optional[MotionOverlayExportConfig] = None


@router.post("/transcribe")
def transcribe_video(req: TranscribeRequest) -> Dict[str, Any]:
    """Transcribe speech in a video using local Whisper and generate kinetic word timestamps."""
    target_path = resolve_media_path(req.video_path)
    lang = req.language if req.language and req.language.lower() != "auto" else None

    logger.info(f"Transcribing {target_path} with language={lang}")
    try:
        result = transcriber.transcribe(str(target_path), language=lang, word_timestamps=True)
    except Exception as e:
        logger.error(f"Whisper transcription error: {e}")
        raise HTTPException(status_code=500, detail=f"Error en transcripción local: {str(e)}")

    # Generate ASS file for the video
    ass_filename = f"editor_sub_{safe_filename(target_path.stem)}.ass"
    ass_path = subtitle_gen.generate_ass_from_segments(
        transcript_segments=result["segments"],
        output_filename=ass_filename,
        sync_mode=req.sync_mode or "word_by_word"
    )

    return {
        "status": "success",
        "video_path": str(target_path),
        "language": result["language"],
        "language_probability": result["language_probability"],
        "duration": result["duration"],
        "full_text": result["full_text"],
        "segments": result["segments"],
        "ass_path": str(ass_path),
        "ass_url": f"/storage/cache/subtitles/{ass_filename}"
    }


@router.post("/transcribe-upload")
async def upload_and_transcribe(
    file: UploadFile = File(...),
    language: Optional[str] = Form(None),
    sync_mode: Optional[str] = Form("word_by_word")
) -> Dict[str, Any]:
    """Upload video directly from OpenCut Studio Pro and transcribe immediately."""
    target_path = await save_upload(file, VIDEO_EXTENSIONS)

    lang = language if language and language.lower() != "auto" else None
    try:
        result = transcriber.transcribe(str(target_path), language=lang, word_timestamps=True)
    except Exception as e:
        logger.error(f"Whisper transcription error: {e}")
        raise HTTPException(status_code=500, detail=f"Error transcribiendo video: {str(e)}")

    ass_filename = f"editor_sub_{safe_filename(target_path.stem)}.ass"
    ass_path = subtitle_gen.generate_ass_from_segments(
        transcript_segments=result["segments"],
        output_filename=ass_filename,
        sync_mode=sync_mode or "word_by_word"
    )

    return {
        "status": "success",
        "video_path": str(target_path),
        "video_url": f"/storage/uploads/{target_path.name}",
        "filename": target_path.name,
        "language": result["language"],
        "duration": result["duration"],
        "full_text": result["full_text"],
        "segments": result["segments"],
        "ass_path": str(ass_path)
    }


@router.post("/export")
def export_editor_video(req: ExportEditorRequest) -> Dict[str, Any]:
    """Render edited clip with filters, speed retime, and baked-in kinetic subtitles using FFmpeg."""
    source_path = resolve_media_path(req.video_path)
    ffmpeg_bin = settings.resolve_ffmpeg_path()

    out_name = f"opencut_export_{uuid.uuid4().hex[:8]}.mp4"
    out_path = settings.OUTPUTS_DIR / out_name
    settings.OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

    # Build video filter chain
    vf_filters = []

    # Aspect ratio & scale
    if req.aspect_ratio == "9:16":
        vf_filters.append("scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black")
    elif req.aspect_ratio == "16:9":
        vf_filters.append("scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black")
    elif req.aspect_ratio == "1:1":
        vf_filters.append("scale=1080:1080:force_original_aspect_ratio=decrease,pad=1080:1080:(ow-iw)/2:(oh-ih)/2:black")

    # Color adjustments (eq filter)
    # eq=brightness=B:contrast=C:saturation=S
    # brightness: -1.0 to 1.0 (0 default) -> map 1.0 to 0.0
    b_val = round((req.brightness - 1.0) * 0.5, 3)
    c_val = round(req.contrast, 3)
    s_val = round(req.saturation, 3)
    if b_val != 0.0 or c_val != 1.0 or s_val != 1.0:
        vf_filters.append(f"eq=brightness={b_val}:contrast={c_val}:saturation={s_val}")

    # Retime speed
    # setpts=(1/speed)*PTS
    if req.speed != 1.0:
        pts_mult = round(1.0 / req.speed, 4)
        vf_filters.append(f"setpts={pts_mult}*PTS")

    # Subtitles burn-in
    if req.include_subtitles and req.transcript_segments:
        style = req.subtitle_style or SubtitleExportStyle()
        ass_filename = f"export_{out_name}.ass"
        ass_path = subtitle_gen.generate_ass_from_segments(
            transcript_segments=req.transcript_segments,
            output_filename=ass_filename,
            font_name=style.font_name,
            font_size=style.font_size,
            highlight_color=sanitize_hex_color(style.highlight_color, "#ffff00"),
            primary_color=sanitize_hex_color(style.primary_color, "#ffffff"),
            margin_v=style.margin_v,
            max_words_per_group=style.max_words_per_group,
            sync_mode=style.sync_mode
        )
        # On Windows FFmpeg, escape colon and backslashes in ass filter path
        escaped_ass = str(Path(ass_path).resolve()).replace("\\", "/").replace(":", "\\:")
        vf_filters.append(f"ass='{escaped_ass}'")

    vf_string = ",".join(vf_filters) if vf_filters else "null"

    # Audio filter for speed
    af_string = _atempo_chain(req.speed) if req.speed != 1.0 else "anull"

    base_render_target = settings.OUTPUTS_DIR / f"base_{out_name}" if req.motion_overlay else out_path

    cmd = [
        ffmpeg_bin,
        "-y",
        "-i", str(source_path),
        "-vf", vf_string,
        "-af", af_string,
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "22",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        str(base_render_target)
    ]

    logger.info(f"Exporting OpenCut Studio clip: {' '.join(cmd)}")
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        logger.error(f"FFmpeg export error: {proc.stderr}")
        raise HTTPException(status_code=500, detail=f"Error renderizando video con FFmpeg: {proc.stderr[:400]}")

    # If motion overlay is requested, composite the motion graphic onto the rendered video
    if req.motion_overlay:
        try:
            logger.info(f"Compositing Motion Graphics overlay ({req.motion_overlay.preset_id}) onto OpenCut export...")
            motion_service.composite_motion_graphic(
                video_path=str(base_render_target),
                preset_id=req.motion_overlay.preset_id,
                params=req.motion_overlay.model_dump(),
                output_path=str(out_path)
            )
        except Exception as e:
            logger.error(f"Error compositing motion overlay in OpenCut: {e}")
            # Fallback to base render target if compositing fails
            if base_render_target.exists():
                shutil.copy2(base_render_target, out_path)
        finally:
            if base_render_target.exists() and base_render_target != out_path:
                try:
                    base_render_target.unlink(missing_ok=True)
                except Exception:
                    pass

    return {
        "status": "success",
        "output_path": str(out_path),
        "filename": out_name,
        "download_url": f"/storage/outputs/{out_name}"
    }


def _atempo_chain(speed: float) -> str:
    """FFmpeg's atempo accepts 0.5–2.0 per instance; chain filters to cover 0.25–4.0."""
    parts = []
    remaining = speed
    while remaining > 2.0:
        parts.append("atempo=2.0")
        remaining /= 2.0
    while remaining < 0.5:
        parts.append("atempo=0.5")
        remaining /= 0.5
    parts.append(f"atempo={round(remaining, 4)}")
    return ",".join(parts)
