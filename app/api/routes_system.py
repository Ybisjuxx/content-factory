import shutil
import logging
from typing import Dict, Any
from fastapi import APIRouter
from app.config import settings
from app.services.semantic_director import SemanticDirector
from app.services.ffmpeg_renderer import FFmpegRenderer
from app.services.comfyui_client import ComfyUIClient

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/system", tags=["System & Doctor Diagnostics"])


@router.get("/health")
def health_check():
    """Quick liveness probe."""
    return {"status": "ok", "app": settings.APP_NAME}


@router.get("/status")
def system_doctor_status() -> Dict[str, Any]:
    """100% Local environment diagnosis: Ollama, faster-whisper, FFmpeg, ComfyUI, and disk space."""
    # 1. Ollama status
    director = SemanticDirector()
    ollama_status = director.check_ollama_status()

    # 2. FFmpeg status
    renderer = FFmpegRenderer()
    ffmpeg_status = renderer.check_ffmpeg()

    # 3. ComfyUI status
    comfyui = ComfyUIClient()
    comfy_status = comfyui.check_health()

    # 4. Storage & Disk
    total, used, free = shutil.disk_usage(settings.STORAGE_DIR)
    free_gb = round(free / (1024 ** 3), 2)

    return {
        "status": "ready" if ffmpeg_status["available"] else "degraded",
        "app_name": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "ollama": ollama_status,
        "faster_whisper": {
            "model_size": settings.WHISPER_MODEL_SIZE,
            "device": settings.WHISPER_DEVICE,
            "compute_type": settings.WHISPER_COMPUTE_TYPE,
            "vad_filter": settings.WHISPER_VAD_FILTER,
        },
        "ffmpeg": ffmpeg_status,
        "comfyui": comfy_status,
        "storage": {
            "root": str(settings.STORAGE_DIR),
            "free_space_gb": free_gb,
            "broll_count": len(list(settings.BROLL_DIR.glob("*.*"))),
            "audio_count": len(list(settings.AUDIO_DIR.glob("*.*"))),
        }
    }
