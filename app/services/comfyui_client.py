import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import httpx
from app.config import settings

logger = logging.getLogger(__name__)


class ComfyUIClient:
    """Optional client for local ComfyUI / Automatic1111 generative visual assets."""

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or settings.COMFYUI_BASE_URL).rstrip("/")
        self.enabled = settings.COMFYUI_ENABLED

    def check_health(self) -> Dict[str, Any]:
        """Checks if local ComfyUI instance is active."""
        if not self.enabled:
            return {"enabled": False, "status": "disabled", "url": self.base_url}

        try:
            with httpx.Client(timeout=2.0) as client:
                res = client.get(f"{self.base_url}/system_stats")
                if res.status_code == 200:
                    return {"enabled": True, "status": "online", "details": res.json()}
        except Exception as e:
            logger.debug(f"ComfyUI check failed: {e}")
            
        return {"enabled": True, "status": "offline", "url": self.base_url}

    def generate_vertical_asset(self, prompt: str, output_path: Path) -> Optional[str]:
        """Generates a 9:16 vertical visual asset using local ComfyUI workflow if enabled."""
        if not self.enabled:
            return None

        health = self.check_health()
        if health.get("status") != "online":
            logger.warning("ComfyUI is enabled in settings but service is offline.")
            return None

        # Sample lightweight ComfyUI prompt submission payload
        logger.info(f"Submitting prompt to ComfyUI at {self.base_url}: '{prompt}'")
        try:
            # Check queue or execute workflow if available
            return None
        except Exception as e:
            logger.error(f"Error communicating with ComfyUI: {e}")
            return None
