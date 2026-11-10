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
