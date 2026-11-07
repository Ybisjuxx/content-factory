import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import create_db_and_tables
from app.api import api_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("video_factory")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown hooks."""
    logger.info("Initializing 100% Local Autonomous Video Factory...")
    settings.ensure_directories()
    create_db_and_tables()
    logger.info("SQLite database and storage directories initialized.")
    yield
    logger.info("Autonomous Video Factory server shutting down.")


app = FastAPI(
    title=settings.APP_NAME,
    description="100% Local Autonomous Video Factory powered by Ollama, faster-whisper, and FFmpeg.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS setup for local interoperability (FastAPI, n8n, local dashboards)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount REST API
app.include_router(api_router, prefix=settings.API_V1_PREFIX)

# Serve static web dashboard
web_index = Path(__file__).resolve().parent.parent / "web" / "index.html"


@app.get("/", response_class=HTMLResponse, tags=["Dashboard"])
def serve_dashboard():
    """Serves the local video factory web management dashboard."""
    if web_index.exists():
        with open(web_index, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Autonomous Video Factory Running</h1><p>Web dashboard not found.</p>")


# Mount storage folder for direct preview access if needed
if settings.STORAGE_DIR.exists():
    app.mount("/storage", StaticFiles(directory=str(settings.STORAGE_DIR)), name="storage")
