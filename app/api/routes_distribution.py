import os
import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
import httpx

from app.config import settings
from app.security import resolve_media_path, validate_webhook_url

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/distribution", tags=["Distribution & Social Uploaders"])


class PublishRequest(BaseModel):
    video_path: str = Field(..., description="Path to rendered MP4 video")
    title: str = Field(..., description="Post title / caption")
    description: str = Field(default="", description="Video description or hashtags")
    platforms: List[str] = Field(default=["n8n"], description="Target platforms: n8n, youtube, tiktok, instagram")
    tags: List[str] = Field(default_factory=list)
    schedule_time: Optional[str] = None
    custom_webhook_url: Optional[str] = None


class ChannelStatus(BaseModel):
    platform: str
    connected: bool
    account_name: Optional[str] = None
    details: str


class PublicationRecord(BaseModel):
    id: str
    video_title: str
    video_path: str
    platforms: List[str]
    status: str  # queued, published, failed
    published_at: str
    dispatch_log: str


# Persistent workflow tracking file
WORKFLOW_FILE = settings.STORAGE_DIR / "video_workflow.json"
# FastAPI runs sync routes in a threadpool: serialise read-modify-write of the JSON store.
_workflow_lock = threading.RLock()


def _youtube_secrets_present() -> bool:
    path = settings.YOUTUBE_CLIENT_SECRET_PATH
    return bool(path) and Path(path).is_file()

def _load_workflow() -> Dict[str, Dict[str, Any]]:
    if WORKFLOW_FILE.exists():
        try:
            with open(WORKFLOW_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Error loading workflow store: {e}")
    return {}

def _save_workflow(data: Dict[str, Dict[str, Any]]) -> None:
    try:
        WORKFLOW_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = WORKFLOW_FILE.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, WORKFLOW_FILE)  # atomic: a crash mid-write no longer wipes the store
    except Exception as e:
        logger.error(f"Error saving workflow store: {e}")

class WorkflowStatusUpdate(BaseModel):
    status: str = Field(..., description="Estado editorial: terminado, descartado, en_edicion, borrador")
    notes: Optional[str] = Field(default="", description="Notas u observaciones de edición")

class ClearQueueRequest(BaseModel):
    scope: str = Field(default="all", description="all, discarded, tests")

# In-memory publication history log for quick dashboard inspection
PUBLICATIONS_LOG: List[Dict[str, Any]] = []


@router.get("/channels", response_model=List[ChannelStatus])
def get_connected_channels():
    """Retorna el estado de conexión de canales de distribución."""
    # Revisar si n8n está activo en el puerto 5678
    n8n_active = False
    try:
        with httpx.Client(timeout=1.5) as client:
            res = client.get("http://localhost:5678/healthz")
            if res.status_code in [200, 401, 403]:
                n8n_active = True
    except Exception:
        pass

    # Revisar credenciales de MoneyPrinter YouTube si existen
    yt_secrets = _youtube_secrets_present()

    return [
        ChannelStatus(
            platform="n8n Local Webhook",
            connected=n8n_active,
            account_name="Local Instance (:5678)" if n8n_active else "Desconectado",
            details="Disparo automático a flujos de trabajo locales de n8n para TikTok/YouTube/Telegram"
        ),
        ChannelStatus(
            platform="YouTube Shorts API",
            connected=yt_secrets,
            account_name="OAuth2 Configurado" if yt_secrets else "Requiere client_secret.json",
            details="Requiere YOUTUBE_CLIENT_SECRET_PATH. La subida directa aún no está implementada: se encola para n8n."
        ),
        ChannelStatus(
            platform="TikTok & Reels (Vía n8n)",
            connected=n8n_active,
            account_name="Gestionado por n8n",
            details="Automatización de subida usando nodos HTTP y API de publicaciones de n8n"
        )
    ]


@router.get("/queue")
def list_publication_queue():
    """Lista las publicaciones recientes y videos listos en el disco para publicar con su estado editorial."""
    output_videos = []
    workflow = _load_workflow()
    
    if settings.OUTPUTS_DIR.exists():
        for f in settings.OUTPUTS_DIR.glob("*.mp4"):
            stat = f.stat()
            size_mb = round(stat.st_size / (1024 * 1024), 2)
            wf = workflow.get(f.name, {})
            # Infer initial status: if not recorded, default to 'en_edicion'
            current_status = wf.get("status") or "en_edicion"
            
            output_videos.append({
                "filename": f.name,
                "path": str(f.resolve()),
                "size_mb": size_mb,
                "created_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                "workflow_status": current_status,
                "notes": wf.get("notes", ""),
                "updated_at": wf.get("updated_at", "")
            })

    output_videos.sort(key=lambda x: x["created_at"], reverse=True)

    return {
        "ready_videos": output_videos,
        "history": PUBLICATIONS_LOG[-20:]
    }


@router.post("/workflow/{filename}/status")
def update_video_workflow_status(filename: str, req: WorkflowStatusUpdate):
    """Actualiza el estado de edición de un video: terminado, descartado, en_edicion."""
    valid_statuses = ["terminado", "descartado", "en_edicion", "borrador"]
    if req.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Estado inválido. Opciones: {valid_statuses}")
    
    filename = os.path.basename(filename)
    video_p = settings.OUTPUTS_DIR / filename
    if not video_p.is_file():
        raise HTTPException(status_code=404, detail=f"Video no encontrado: {filename}")

    with _workflow_lock:
        workflow = _load_workflow()
        workflow[filename] = {
            "status": req.status,
            "notes": (req.notes or "")[:2000],
            "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        }
        _save_workflow(workflow)
    
    return {
        "status": "success",
        "filename": filename,
        "workflow_status": req.status,
        "notes": req.notes,
        "updated_at": workflow[filename]["updated_at"]
    }


@router.delete("/queue/{filename}")
def delete_queue_video(filename: str):
    """Elimina un archivo de video específico de storage/outputs/ y remueve su registro de workflow."""
    # Sanitize filename
    clean_name = os.path.basename(filename)
    video_p = settings.OUTPUTS_DIR / clean_name
    
    if not video_p.exists():
        raise HTTPException(status_code=404, detail=f"Video no encontrado: {clean_name}")
        
    try:
        video_p.unlink()
        with _workflow_lock:
            workflow = _load_workflow()
            if clean_name in workflow:
                del workflow[clean_name]
                _save_workflow(workflow)
        logger.info(f"Video {clean_name} eliminado exitosamente de la cola.")
        return {"status": "success", "message": f"Video {clean_name} eliminado."}
    except Exception as e:
        logger.error(f"Error eliminando video {clean_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Error al eliminar video: {str(e)}")


@router.post("/queue/clear")
def clear_publication_queue(req: ClearQueueRequest = ClearQueueRequest()):
    """Limpia la cola de videos. Scope puede ser 'all' (todos los videos de prueba) o 'discarded' (solo descartados)."""
    if req.scope not in {"all", "discarded", "tests"}:
        raise HTTPException(status_code=400, detail="scope debe ser 'all', 'discarded' o 'tests'.")
    with _workflow_lock:
        return _clear_queue_locked(req)


def _clear_queue_locked(req: ClearQueueRequest) -> Dict[str, Any]:
    deleted_count = 0
    errors = []
    workflow = _load_workflow()
    
    if settings.OUTPUTS_DIR.exists():
        for f in list(settings.OUTPUTS_DIR.glob("*.mp4")):
            wf_status = workflow.get(f.name, {}).get("status", "en_edicion")
            
            should_delete = False
            if req.scope == "all":
                should_delete = True
            elif req.scope == "discarded" and wf_status == "descartado":
                should_delete = True
            elif req.scope == "tests" and ("test" in f.name.lower() or "export" in f.name.lower() or "mg_" in f.name.lower()):
                should_delete = True
                
            if should_delete:
                try:
                    f.unlink()
                    deleted_count += 1
                    if f.name in workflow:
                        del workflow[f.name]
                except Exception as e:
                    errors.append(f"{f.name}: {str(e)}")
                    
    _save_workflow(workflow)
    
    # Also clean publications history if clearing all
    if req.scope == "all":
        PUBLICATIONS_LOG.clear()
        
    return {
        "status": "success",
        "deleted_count": deleted_count,
        "scope": req.scope,
        "errors": errors
    }


@router.delete("/history/{record_id}")
def delete_publication_history(record_id: str):
    """Elimina un registro del historial de publicaciones."""
    global PUBLICATIONS_LOG
    initial_len = len(PUBLICATIONS_LOG)
    PUBLICATIONS_LOG = [p for p in PUBLICATIONS_LOG if p.get("id") != record_id]
    if len(PUBLICATIONS_LOG) == initial_len:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    return {"status": "success", "message": f"Registro {record_id} eliminado"}


@router.post("/publish")
def publish_video(req: PublishRequest):
    """Envía un video a los canales de distribución configurados (n8n, YouTube, etc.)."""
    video_p = resolve_media_path(req.video_path)
    custom_webhook = validate_webhook_url(req.custom_webhook_url)

    log_messages = []
    success_platforms = []

    # 1. Enviar a n8n
    if "n8n" in req.platforms:
        target_url = custom_webhook or settings.N8N_DEFAULT_WEBHOOK_URL or "http://localhost:5678/webhook/publish-video"
        payload = {
            "event": "content_factory.publish_request",
            "video_path": str(video_p.resolve()),
            "video_filename": video_p.name,
            "title": req.title,
            "description": req.description,
            "tags": req.tags,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        try:
            with httpx.Client(timeout=4.0) as client:
                res = client.post(target_url, json=payload)
                log_messages.append(f"n8n Webhook: HTTP {res.status_code}")
                if res.is_success:  # a 404/500 from n8n is not a successful publish
                    success_platforms.append("n8n")
        except Exception as e:
            log_messages.append(f"n8n Webhook no respondió en {target_url} ({e})")

    # 2. Enviar a YouTube (MoneyPrinter uploader hook)
    if "youtube" in req.platforms:
        # No uploader is implemented yet: never report this as "published".
        if _youtube_secrets_present():
            log_messages.append("YouTube: credenciales encontradas, pero la subida directa no está implementada (usa n8n).")
        else:
            log_messages.append("YouTube: configura YOUTUBE_CLIENT_SECRET_PATH (subida directa no implementada).")

    record = {
        "id": f"pub-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
        "video_title": req.title,
        "video_path": str(video_p),
        "platforms": req.platforms,
        "status": "published" if success_platforms else "queued",
        "published_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "dispatch_log": "; ".join(log_messages) if log_messages else "Encolado para distribución"
    }
    PUBLICATIONS_LOG.append(record)

    return {
        "status": "success",
        "message": "Solicitud de publicación procesada",
        "record": record
    }
