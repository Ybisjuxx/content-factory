import os
import shutil
from pathlib import Path
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _detect_default_ffmpeg() -> str:
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg
    try:
        import imageio_ffmpeg
        bundled = imageio_ffmpeg.get_ffmpeg_exe()
        if bundled and os.path.exists(bundled):
            return bundled
    except Exception:
        pass
    return "ffmpeg"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    APP_NAME: str = "Content Factory (100% Local)"
    APP_ENV: str = "production"
    API_V1_PREFIX: str = "/api/v1"
    PORT: int = 8000
    HOST: str = "127.0.0.1"

    # Paths: only STORAGE_DIR is configurable; every sub-directory is derived from it
    # (see properties below) so a single env var relocates all state (useful for tests).
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    STORAGE_DIR: Path = Path(__file__).resolve().parent.parent / "storage"
    DATABASE_URL: Optional[str] = None

    # Security (local-first, but the browser is an attack surface: CORS, DNS rebinding, SSRF)
    CORS_ORIGINS: List[str] = [
        "http://127.0.0.1:8000",
        "http://localhost:8000",
        "http://127.0.0.1:5678",
        "http://localhost:5678",
    ]
    ALLOWED_HOSTS: List[str] = ["127.0.0.1", "localhost", "[::1]"]
    # Extra directories (besides storage/) from which input videos may be read
    # and to which explicit output paths may be written. Empty = storage only.
    ALLOWED_MEDIA_DIRS: List[Path] = []
    # Hosts that outbound webhooks (n8n) may target. Prevents SSRF from API callers.
    WEBHOOK_ALLOWED_HOSTS: List[str] = ["localhost", "127.0.0.1", "::1"]
    MAX_UPLOAD_MB: int = 2048
    MAX_CONCURRENT_JOBS: int = 1

    # External integrations
    YOUTUBE_CLIENT_SECRET_PATH: Optional[Path] = None
    TRENDS_LIVE_FETCH_ENABLED: bool = True

    # Ollama Semantic Director
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    OLLAMA_MODEL: str = "qwen2.5:7b-instruct"
    OLLAMA_FALLBACK_MODEL: str = "llama3.1:8b-instruct"
    OLLAMA_TIMEOUT_SECONDS: float = 60.0

    # faster-whisper
    WHISPER_MODEL_SIZE: str = "base"
    WHISPER_DEVICE: str = "cpu"  # cpu, cuda, auto
    WHISPER_COMPUTE_TYPE: str = "int8"
    WHISPER_VAD_FILTER: bool = True
    WHISPER_MIN_SILENCE_DURATION_MS: int = 500

    # Audio & Video Rendering
    FFMPEG_PATH: str = Field(default_factory=_detect_default_ffmpeg)
    FFPROBE_PATH: Optional[str] = None
    AUDIO_CROSSFADE_SECONDS: float = 0.02  # 20ms click-free crossfade
    AUDIO_DUCKING_DB: float = -22.0  # Ambient audio ducked to -22 dB
    AUDIO_DUCKING_ATTACK_MS: int = 20
    AUDIO_DUCKING_RELEASE_MS: int = 300
    TARGET_WIDTH: int = 1080
    TARGET_HEIGHT: int = 1920
    TARGET_FPS: int = 30

    # Subtitles Styling (Kinetic vertical ASS)
    SUBTITLE_FONT_NAME: str = "Impact"
    SUBTITLE_FONT_SIZE: int = 24
    SUBTITLE_PRIMARY_COLOR: str = "&H00FFFFFF"  # White (&HAABBGGRR)
    SUBTITLE_HIGHLIGHT_COLOR: str = "&H0000FFFF"  # Vibrant Yellow
    SUBTITLE_OUTLINE_COLOR: str = "&H00000000"  # Black border
    SUBTITLE_BACK_COLOR: str = "&H80000000"  # Subtle shadow
    SUBTITLE_BOTTOM_MARGIN: int = 420  # Safe zone margin for TikTok/Reels UI

    # ComfyUI / Automatic1111 Optional Hook
    COMFYUI_ENABLED: bool = False
    COMFYUI_BASE_URL: str = "http://127.0.0.1:8188"

    # n8n Webhook Integration
    N8N_DEFAULT_WEBHOOK_URL: Optional[str] = None

    @property
    def BROLL_DIR(self) -> Path:
        return self.STORAGE_DIR / "broll_library"

    @property
    def AUDIO_DIR(self) -> Path:
        return self.STORAGE_DIR / "audio_library"

    @property
    def CACHE_DIR(self) -> Path:
        return self.STORAGE_DIR / "cache"

    @property
    def OUTPUTS_DIR(self) -> Path:
        return self.STORAGE_DIR / "outputs"

    @property
    def UPLOADS_DIR(self) -> Path:
        return self.STORAGE_DIR / "uploads"

    @property
    def DATABASE_PATH(self) -> Path:
        return self.STORAGE_DIR / "content_factory.db"

    def media_roots(self) -> List[Path]:
        """Directories the API may read media from / write renders to."""
        roots = [self.UPLOADS_DIR, self.OUTPUTS_DIR, self.BROLL_DIR, self.AUDIO_DIR, self.CACHE_DIR]
        return [p.resolve() for p in roots + list(self.ALLOWED_MEDIA_DIRS)]

    def ensure_directories(self) -> None:
        """Create storage directories if they do not exist."""
        for path in [self.STORAGE_DIR, self.BROLL_DIR, self.AUDIO_DIR, self.CACHE_DIR, self.OUTPUTS_DIR, self.UPLOADS_DIR]:
            path.mkdir(parents=True, exist_ok=True)

    def resolve_ffmpeg_path(self) -> str:
        """Find the best available ffmpeg executable."""
        if self.FFMPEG_PATH and os.path.exists(self.FFMPEG_PATH):
            return self.FFMPEG_PATH
        
        system_ffmpeg = shutil.which("ffmpeg")
        if system_ffmpeg:
            return system_ffmpeg
            
        try:
            import imageio_ffmpeg
            bundled = imageio_ffmpeg.get_ffmpeg_exe()
            if bundled and os.path.exists(bundled):
                return bundled
        except Exception:
            pass
            
        return "ffmpeg"

    def resolve_ffprobe_path(self) -> Optional[str]:
        """Find ffprobe if available."""
        if self.FFPROBE_PATH and os.path.exists(self.FFPROBE_PATH):
            return self.FFPROBE_PATH
        return shutil.which("ffprobe")


settings = Settings()
settings.ensure_directories()
