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


def test_list_all_presets_and_flip_card_stack():
    res = client.get("/api/v1/motion-graphics/presets")
    assert res.status_code == 200
    presets = res.json()
    assert len(presets) >= 110
    ids = [p["id"] for p in presets]
    assert "flip_card_stack" in ids
    assert "retention_bar" in ids
    assert "split_chars_stagger" in ids
    assert "proximity_scale_grid" in ids
    assert "velocity_skew" in ids
    assert "scrubbed_bento_gallery" in ids
    assert "directional_marquee" in ids
    assert "cursor_tilt_3d" in ids
    assert "physics_confetti_burst" in ids

    # Verify all 75 CodePen presets from catalog are present
    codepen_presets = [p for p in presets if p.get("default_params", {}).get("codepen_url")]
    assert len(codepen_presets) >= 75

    # Test preview of proximity_scale_grid (CodePen zxKyeEm)
    prox_res = client.post("/api/v1/motion-graphics/preview", json={
        "preset_id": "proximity_scale_grid",
        "params": {
            "headline": "TEST PROXIMITY",
            "accent_color": "#38BDF8"
        }
    })
    assert prox_res.status_code == 200
    assert "TEST PROXIMITY" in prox_res.json()["svg"]

    # Test preview and overlay generation of an imported GSAP CodePen catalog preset
    demo_sample = next(p for p in presets if p["id"].startswith("gsap_"))
    prev_res = client.post("/api/v1/motion-graphics/preview", json={
        "preset_id": demo_sample["id"],
        "params": demo_sample["default_params"]
    })
    assert prev_res.status_code == 200
    assert "GSAP CODEPEN" in prev_res.json()["svg"]

    # Test PNG generation of the catalog preset
    service = MotionGraphicsService()
    png_p = service.generate_overlay_png(demo_sample["id"], demo_sample["default_params"])
    assert png_p.exists()
    assert png_p.stat().st_size > 5000
    png_p.unlink()


def test_custom_preset_crud_lifecycle(tmp_path):
    # Test adding a custom preset via API
    new_preset = {
        "id": "test_custom_countdown",
        "name": "Custom Dynamic Countdown",
        "category": "Retención & Cues",
        "description": "Preset importado para pruebas",
        "default_params": {
            "headline": "CUENTA REGRESIVA",
            "accent_color": "#EC4899",
            "duration": 5.0,
            "codepen_url": "https://codepen.io/GreenSock/pen/Yzdzxem"
        }
    }
    create_res = client.post("/api/v1/motion-graphics/presets", json=new_preset)
    assert create_res.status_code == 200
    created = create_res.json()
    assert created["status"] == "success"
    assert created["preset"]["id"] == "test_custom_countdown"

    # Verify preset appears in list
    list_res = client.get("/api/v1/motion-graphics/presets")
    assert any(p["id"] == "test_custom_countdown" for p in list_res.json())

    # Delete custom preset
    del_res = client.delete("/api/v1/motion-graphics/presets/test_custom_countdown")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "success"


def test_retention_bar_dynamic_composite_ffmpeg(tmp_path):
    from app.config import settings
    import subprocess
    ffmpeg_bin = settings.resolve_ffmpeg_path()
    dummy_video = tmp_path / "dummy_bar.mp4"
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
        preset_id="retention_bar",
        params={
            "bar_color": "#38BDF8",
            "height_px": 16,
            "start_time": 0.0,
            "duration": 2.0
        },
        output_path=str(tmp_path / "out_retention_bar.mp4")
    )
    assert Path(out_video).exists()
    assert Path(out_video).stat().st_size > 1000

