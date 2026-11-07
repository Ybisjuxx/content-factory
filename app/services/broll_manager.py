import os
import json
import logging
import re
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional
from sqlmodel import Session, select
from app.config import settings
from app.models.asset import Asset, AssetType

logger = logging.getLogger(__name__)


class LocalBrollManager:
    """Manages indexing, metadata extraction, and semantic selection of local stock B-roll assets."""

    def __init__(self, library_dir: Optional[Path] = None):
        self.library_dir = library_dir or settings.BROLL_DIR
        self.library_dir.mkdir(parents=True, exist_ok=True)

    def index_library(self, session: Optional[Session] = None) -> List[Asset]:
        """Scans the B-roll directory, extracts metadata and tags, and updates the local database."""
        valid_extensions = {".mp4", ".mov", ".mkv", ".webm", ".png", ".jpg", ".jpeg"}
        discovered_assets: List[Asset] = []

        logger.info(f"Scanning B-roll directory: {self.library_dir}")
        for root, _, files in os.walk(self.library_dir):
            for file in files:
                file_path = Path(root) / file
                if file_path.suffix.lower() not in valid_extensions:
                    continue

                tags = self._extract_tags(file_path)
                meta = self._probe_media(file_path)
                
                asset = Asset(
                    name=file_path.stem,
                    file_path=str(file_path.resolve()),
                    asset_type=AssetType.BROLL if file_path.suffix.lower() in [".mp4", ".mov", ".mkv", ".webm"] else AssetType.IMAGE,
                    tags=",".join(tags),
                    duration_seconds=meta.get("duration"),
                    width=meta.get("width"),
                    height=meta.get("height"),
                    is_vertical=meta.get("is_vertical", True),
                )
                discovered_assets.append(asset)

        if session:
            # Sync with database
            for asset in discovered_assets:
                existing = session.exec(
                    select(Asset).where(Asset.file_path == asset.file_path)
                ).first()
                if not existing:
                    session.add(asset)
                else:
                    existing.tags = asset.tags
                    existing.duration_seconds = asset.duration_seconds
                    existing.width = asset.width
                    existing.height = asset.height
                    existing.is_vertical = asset.is_vertical
                    session.add(existing)
            session.commit()
            logger.info(f"Indexed {len(discovered_assets)} B-roll assets in SQLite database.")

        return discovered_assets

    def select_broll_for_cue(self, query: str, session: Optional[Session] = None) -> Optional[Asset]:
        """Finds the best matching B-roll asset for a given semantic topic or keyword."""
        assets: List[Asset] = []
        if session:
            assets = list(session.exec(select(Asset)).all())
        else:
            assets = self.index_library()

        if not assets:
            logger.info("No user B-roll assets found; generating a dynamic sample procedural clip.")
            sample_asset = self._ensure_sample_asset()
            return sample_asset

        query_terms = set(re.findall(r"\w+", query.lower()))

        best_score = -1
        best_asset = assets[0]

        for asset in assets:
            asset_tags = set(t.strip().lower() for t in asset.tags.split(",") if t.strip())
            asset_words = set(re.findall(r"\w+", asset.name.lower()))
            combined = asset_tags.union(asset_words)

            score = len(query_terms.intersection(combined))
            # Prefer 9:16 vertical clips
            if asset.is_vertical:
                score += 1

            if score > best_score:
                best_score = score
                best_asset = asset

        return best_asset

    def _extract_tags(self, path: Path) -> List[str]:
        """Derives semantic tags from file names, parent folders, or sidecar json."""
        tags = set()

        # Check sidecar JSON
        sidecar = path.with_suffix(".json")
        if sidecar.exists():
            try:
                with open(sidecar, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for t in data.get("tags", []):
                        tags.add(t.strip().lower())
            except Exception:
                pass

        # Split path parts
        rel_parts = path.relative_to(self.library_dir).parts
        for part in rel_parts[:-1]:
            for word in re.findall(r"[a-zA-Z0-9]+", part):
                if len(word) > 2:
                    tags.add(word.lower())

        # Split filename
        for word in re.findall(r"[a-zA-Z0-9]+", path.stem):
            if len(word) > 2 and word.lower() not in ["mp4", "mov", "vertical", "short"]:
                tags.add(word.lower())

        return sorted(list(tags))

    def _probe_media(self, path: Path) -> Dict[str, Any]:
        """Reads width, height, duration using ffprobe if available or defaults."""
        ffprobe_bin = settings.resolve_ffprobe_path()
        if not ffprobe_bin:
            # Fallback estimation for 9:16 vertical defaults
            return {"width": 1080, "height": 1920, "duration": 5.0, "is_vertical": True}

        cmd = [
            ffprobe_bin,
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,duration:format=duration",
            "-of", "json",
            str(path)
        ]
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res.returncode == 0:
                data = json.loads(res.stdout)
                streams = data.get("streams", [])
                format_info = data.get("format", {})
                w = streams[0].get("width", 1080) if streams else 1080
                h = streams[0].get("height", 1920) if streams else 1920
                dur = float(streams[0].get("duration") or format_info.get("duration") or 5.0)
                return {
                    "width": w,
                    "height": h,
                    "duration": dur,
                    "is_vertical": h >= w
                }
        except Exception as e:
            logger.debug(f"ffprobe media probe error for {path}: {e}")

        return {"width": 1080, "height": 1920, "duration": 5.0, "is_vertical": True}

    def _ensure_sample_asset(self) -> Asset:
        """Generates a high-quality vertical 9:16 sample B-roll clip if library is empty."""
        sample_path = self.library_dir / "sample_tech_grid_916.mp4"
        if not sample_path.exists():
            ffmpeg_bin = settings.resolve_ffmpeg_path()
            cmd = [
                ffmpeg_bin,
                "-y",
                "-f", "lavfi",
                "-i", "testsrc=size=1080x1920:rate=30",
                "-vf", "hue=s=0,eq=contrast=1.5:brightness=-0.2,drawgrid=width=100:height=100:thickness=2:color=cyan@0.3",
                "-t", "5",
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                str(sample_path)
            ]
            try:
                subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            except Exception as e:
                logger.warning(f"Could not generate procedural sample B-roll: {e}")

        return Asset(
            name="sample_tech_grid_916",
            file_path=str(sample_path.resolve()),
            asset_type=AssetType.BROLL,
            tags="tech,grid,coding,future,digital",
            duration_seconds=5.0,
            width=1080,
            height=1920,
            is_vertical=True
        )
