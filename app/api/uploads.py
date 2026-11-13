"""Shared, size-limited upload handling (was duplicated in two routers)."""
import logging
import uuid
from pathlib import Path
from typing import Iterable

from fastapi import HTTPException, UploadFile

from app.config import settings
from app.security import safe_filename

logger = logging.getLogger(__name__)

VIDEO_EXTENSIONS = frozenset({".mp4", ".mov", ".mkv", ".webm", ".avi"})
_CHUNK = 1024 * 1024


async def save_upload(file: UploadFile, allowed_exts: Iterable[str]) -> Path:
    """Stream ``file`` into storage/uploads with a sanitised unique name and a size cap."""
    allowed = set(allowed_exts)
    ext = Path(file.filename or "").suffix.lower()
    if ext not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Formato no compatible ({ext or 'sin extensión'}). Usa: {', '.join(sorted(allowed))}",
        )

    settings.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    target = settings.UPLOADS_DIR / f"{uuid.uuid4().hex[:8]}_{safe_filename(file.filename)}"
    limit = settings.MAX_UPLOAD_MB * 1024 * 1024
    written = 0
    try:
        with open(target, "wb") as out:
            while chunk := await file.read(_CHUNK):
                written += len(chunk)
                if written > limit:
                    raise HTTPException(status_code=413, detail=f"El archivo supera {settings.MAX_UPLOAD_MB} MB.")
                out.write(chunk)
    except HTTPException:
        target.unlink(missing_ok=True)
        raise
    except Exception as e:
        target.unlink(missing_ok=True)
        logger.error(f"Error saving upload: {e}")
        raise HTTPException(status_code=500, detail="Error guardando el archivo.")
    return target
