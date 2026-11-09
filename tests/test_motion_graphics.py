import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app.services.motion_graphics import MotionGraphicsService

client = TestClient(app)


def test_list_motion_graphics_presets():
    res = client.get("/api/v1/motion-graphics/presets")
    assert res.status_code == 200
    presets = res.json()
    assert len(presets) >= 4
    preset_ids = [p["id"] for p in presets]
    assert "lower_third_glass" in preset_ids
    assert "stat_callout_neon" in preset_ids
    assert "viral_hook" in preset_ids


def test_preview_motion_graphic_svg():
    payload = {
        "preset_id": "lower_third_glass",
        "params": {
            "title": "JUAN PEREZ",
            "subtitle": "Tech Lead",
            "accent_color": "#38BDF8"
        },
        "width": 1080,
        "height": 1920
    }
    res = client.post("/api/v1/motion-graphics/preview", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "svg" in data
    assert "JUAN PEREZ" in data["svg"]
    assert "#38BDF8" in data["svg"]


def test_generate_overlay_png_generation():
    service = MotionGraphicsService()
    png_path = service.generate_overlay_png(
        preset_id="stat_callout_neon",
        params={
            "metric": "+500%",
            "explanation": "Crecimiento de audiencia",
            "badge": "VIRAL",
            "accent_color": "#10B981"
        }
    )
    assert png_path.exists()
    assert png_path.stat().st_size > 1000
    png_path.unlink()


def test_composite_motion_graphic_ffmpeg(tmp_path):
    # Create a 2s dummy video
    from app.config import settings
    import subprocess
    ffmpeg_bin = settings.resolve_ffmpeg_path()
    dummy_video = tmp_path / "dummy.mp4"
    cmd = [
        ffmpeg_bin, "-y",
        "-f", "lavfi", "-i", "color=c=black:s=1080x1920:d=2:r=30",
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
        "-t", "2",
        "-c:v", "libx264", "-c:a", "aac",
        str(dummy_video)
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

    service = MotionGraphicsService(cache_dir=tmp_path / "cache")
    out_video = service.composite_motion_graphic(
        video_path=str(dummy_video),
        preset_id="lower_third_glass",
        params={
            "title": "TEST SPEAKER",
            "subtitle": "Test Role",
            "start_time": 0.2,
            "duration": 1.5
        },
        output_path=str(tmp_path / "out_mg.mp4")
    )
    assert Path(out_video).exists()
    assert Path(out_video).stat().st_size > 1000
