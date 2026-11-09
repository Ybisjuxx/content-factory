import logging
import shutil
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, File, UploadFile, HTTPException, Query
from pydantic import BaseModel, Field
from app.config import settings
from app.services.motion_graphics import MotionGraphicsService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/motion-graphics", tags=["Motion Graphics & Video Upload"])

mg_service = MotionGraphicsService()


class PreviewRequest(BaseModel):
    preset_id: str
    params: Dict[str, Any] = Field(default_factory=dict)
    width: int = 1080
    height: int = 1920


class ApplyMotionGraphicsRequest(BaseModel):
    video_path: str
    preset_id: str
    params: Dict[str, Any] = Field(default_factory=dict)
    output_path: Optional[str] = None


@router.get("/presets")
def list_presets() -> List[Dict[str, Any]]:
    """Returns all available motion graphics presets inspired by HyperFrames."""
    return mg_service.get_presets()


@router.post("/upload")
async def upload_recorded_video(file: UploadFile = File(...)) -> Dict[str, Any]:
    """Upload a user-recorded video to the local factory storage."""
    allowed_exts = {".mp4", ".mov", ".mkv", ".webm", ".avi"}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed_exts:
        raise HTTPException(
            status_code=400,
            detail=f"Formato no compatible ({ext}). Por favor sube archivos {', '.join(allowed_exts)}"
        )

    settings.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    safe_filename = f"{uuid.uuid4().hex[:8]}_{Path(file.filename).name.replace(' ', '_')}"
    target_path = settings.UPLOADS_DIR / safe_filename

    try:
        with open(target_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        logger.error(f"Error saving uploaded video: {e}")
        raise HTTPException(status_code=500, detail=f"Error guardando el video: {e}")

    # Probe video
    try:
        meta = mg_service.probe_video(str(target_path))
        return {
            "status": "success",
            "message": "Video subido correctamente al almacenamiento local.",
            "metadata": meta,
            "preview_url": f"/storage/uploads/{target_path.name}"
        }
    except Exception as e:
        logger.warning(f"Failed to probe uploaded video: {e}")
        return {
            "status": "success",
            "message": "Video subido, pero no se pudo leer metadatos detallados.",
            "path": str(target_path),
            "filename": target_path.name,
            "preview_url": f"/storage/uploads/{target_path.name}"
        }


@router.get("/uploads")
def list_uploaded_videos() -> List[Dict[str, Any]]:
    """List all previously uploaded user videos."""
    if not settings.UPLOADS_DIR.exists():
        return []

    videos = []
    for f in settings.UPLOADS_DIR.glob("*.*"):
        if f.suffix.lower() in {".mp4", ".mov", ".mkv", ".webm", ".avi"}:
            videos.append({
                "filename": f.name,
                "path": str(f.resolve()),
                "size_mb": round(f.stat().st_size / (1024 * 1024), 2),
                "url": f"/storage/uploads/{f.name}"
            })
    return sorted(videos, key=lambda x: x["filename"], reverse=True)


@router.post("/preview")
def preview_motion_graphic(req: PreviewRequest) -> Dict[str, Any]:
    """Generates an SVG preview markup for instant browser display."""
    svg_markup = mg_service.generate_preview_svg(
        preset_id=req.preset_id,
        params=req.params,
        width=req.width,
        height=req.height
    )
    return {"preset_id": req.preset_id, "svg": svg_markup}


@router.post("/apply")
def apply_motion_graphic(req: ApplyMotionGraphicsRequest) -> Dict[str, Any]:
    """Applies a selected motion graphic overlay onto the user video using local FFmpeg."""
    if not Path(req.video_path).exists():
        raise HTTPException(status_code=404, detail=f"No se encontró el video: {req.video_path}")

    try:
        out_path = mg_service.composite_motion_graphic(
            video_path=req.video_path,
            preset_id=req.preset_id,
            params=req.params,
            output_path=req.output_path
        )
        out_file = Path(out_path)
        return {
            "status": "completed",
            "message": "Motion graphic integrado exitosamente en el video.",
            "output_path": str(out_file),
            "filename": out_file.name,
            "preview_url": f"/storage/outputs/{out_file.name}",
            "size_mb": round(out_file.stat().st_size / (1024 * 1024), 2)
        }
    except Exception as e:
        logger.error(f"Error applying motion graphic: {e}")
        raise HTTPException(status_code=500, detail=f"Error en renderizado de motion graphics: {e}")
