import sys
import logging
from contextlib import asynccontextmanager
from pathlib import Path

# Fix for Windows asyncio [WinError 10054] ConnectionResetError on browser media cancels
if sys.platform == "win32":
    try:
        from asyncio.proactor_events import _ProactorBasePipeTransport
        _orig_call_connection_lost = _ProactorBasePipeTransport._call_connection_lost

        def _silenced_call_connection_lost(self, exc):
            try:
                _orig_call_connection_lost(self, exc)
            except (ConnectionResetError, OSError):
                pass

        _ProactorBasePipeTransport._call_connection_lost = _silenced_call_connection_lost
    except Exception:
        pass

# Ensure project root is in sys.path regardless of execution environment
_root_dir = str(Path(__file__).resolve().parent.parent)
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import create_db_and_tables, engine
from app.api import api_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("video_factory")


def _fail_orphaned_jobs() -> None:
    """Jobs run as in-process background tasks: a restart kills them silently and they
    stayed 'rendering' forever in the dashboard. Mark them failed on startup."""
    from datetime import datetime, timezone
    from sqlmodel import Session, select
    from app.models.job import Job, JobStatus

    active = [JobStatus.QUEUED, JobStatus.TRANSCRIBING, JobStatus.DIRECTING,
              JobStatus.SELECTING_ASSETS, JobStatus.RENDERING]
    with Session(engine) as session:
        jobs = session.exec(select(Job).where(Job.status.in_(active))).all()
        for job in jobs:
            job.status = JobStatus.FAILED
            job.error_message = "Interrumpido por reinicio del servidor. Vuelve a lanzarlo."
            job.current_step = "Interrumpido"
            job.updated_at = datetime.now(timezone.utc)
            session.add(job)
        session.commit()
        if jobs:
            logger.warning(f"Marked {len(jobs)} orphaned job(s) as failed after restart.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown hooks."""
    logger.info("Initializing 100% Local Autonomous Video Factory...")
    settings.ensure_directories()
    create_db_and_tables()
    _fail_orphaned_jobs()
    logger.info("SQLite database and storage directories initialized.")
    yield
    logger.info("Autonomous Video Factory server shutting down.")


app = FastAPI(
    title=settings.APP_NAME,
    description="100% Local Autonomous Video Factory powered by Ollama, faster-whisper, and FFmpeg.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS: only the dashboard itself and local n8n may call the API from a browser.
# A wildcard origin with credentials let any website drive the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)
# Host header allow-list blocks DNS-rebinding attacks against the loopback server.
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    if request.url.path.startswith("/storage/"):
        # User media is never meant to run script in the dashboard origin.
        response.headers.setdefault("Content-Security-Policy", "default-src 'none'; media-src 'self'; style-src 'unsafe-inline'; sandbox")
    return response


# Mount REST API
app.include_router(api_router, prefix=settings.API_V1_PREFIX)

# Serve static web dashboard
web_dir = Path(__file__).resolve().parent.parent / "web"
web_index = web_dir / "index.html"


@app.get("/", response_class=HTMLResponse, tags=["Dashboard"])
def serve_dashboard():
    """Serves the local video factory web management dashboard."""
    if web_index.exists():
        return FileResponse(web_index, media_type="text/html")
    return HTMLResponse("<h1>Autonomous Video Factory Running</h1><p>Web dashboard not found.</p>")


# Mount static web directory for vendor scripts, icons, etc.
if web_dir.exists():
    app.mount("/web", StaticFiles(directory=str(web_dir)), name="web")

# Expose ONLY media folders. Mounting all of storage/ leaked the SQLite DB,
# workflow JSON, server.log and user-controlled SVG files.
settings.ensure_directories()
(settings.CACHE_DIR / "subtitles").mkdir(parents=True, exist_ok=True)
for _sub, _path in {
    "uploads": settings.UPLOADS_DIR,
    "outputs": settings.OUTPUTS_DIR,
    "cache/subtitles": settings.CACHE_DIR / "subtitles",
}.items():
    app.mount(f"/storage/{_sub}", StaticFiles(directory=str(_path)), name=f"storage-{_sub.replace('/', '-')}")
