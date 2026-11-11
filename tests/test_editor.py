import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_transcribe_endpoint_with_uploaded_file():
    # Test with user's uploaded video if available, or synthetic check
    upload_video = Path("storage/uploads/ec34f03a_WhatsApp_Video_2026-11-09_at_11.25.42_PM.mp4")
    if not upload_video.exists():
        pytest.skip("Test video not available")

    response = client.post(
        "/api/v1/editor/transcribe",
        json={"video_path": str(upload_video), "language": "es"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["language"] == "es"
    assert "panz" in data["full_text"].lower() or len(data["segments"]) > 0
    assert len(data["segments"]) >= 1
    assert "words" in data["segments"][0]


def test_export_endpoint_with_motion_overlay():
    test_video = Path("storage/broll_library/digital_growth_chart_vertical.mp4")
    if not test_video.exists():
        pytest.skip("Test broll video not available")

    response = client.post(
        "/api/v1/editor/export",
        json={
            "video_path": str(test_video),
            "aspect_ratio": "9:16",
            "speed": 1.0,
            "brightness": 1.0,
            "contrast": 1.0,
            "saturation": 1.0,
            "include_subtitles": False,
            "motion_overlay": {
                "preset_id": "lower_third_glass",
                "title": "ALEX RIVERA",
                "subtitle": "Ingeniero en IA",
                "badge": "SPEAKER",
                "accent_color": "#38BDF8",
                "start_time": 0.5,
                "duration": 2.0
            }
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "output_path" in data
    assert Path(data["output_path"]).exists()
    assert data["download_url"].startswith("/storage/outputs/")

