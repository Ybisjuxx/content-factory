import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings

client = TestClient(app)


def test_distribution_channels():
    res = client.get("/api/v1/distribution/channels")
    assert res.status_code == 200
    channels = res.json()
    assert isinstance(channels, list)
    platforms = [c["platform"] for c in channels]
    assert "YouTube Shorts API" in platforms or "n8n Local Webhook" in platforms


def test_distribution_queue_and_workflow_lifecycle():
    # 1. Create a dummy test video in settings.OUTPUTS_DIR
    settings.OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    test_video_name = "test_workflow_dummy_video.mp4"
    test_video_path = settings.OUTPUTS_DIR / test_video_name
    test_video_path.write_bytes(b"\x00" * 1024)  # 1 KB dummy file

    try:
        # 2. Get queue and verify the dummy video appears
        res = client.get("/api/v1/distribution/queue")
        assert res.status_code == 200
        data = res.json()
        assert "ready_videos" in data
        matching = [v for v in data["ready_videos"] if v["filename"] == test_video_name]
        assert len(matching) == 1
        video_data = matching[0]
        assert "workflow_status" in video_data

        # 3. Update status to 'en_edicion'
        res = client.post(
            f"/api/v1/distribution/workflow/{test_video_name}/status",
            json={"status": "en_edicion", "notes": "Ajustando color y subtitulos"}
        )
        assert res.status_code == 200
        assert res.json()["workflow_status"] == "en_edicion"

        # Verify queue reflects the change
        res = client.get("/api/v1/distribution/queue")
        matching = [v for v in res.json()["ready_videos"] if v["filename"] == test_video_name]
        assert matching[0]["workflow_status"] == "en_edicion"
        assert matching[0]["notes"] == "Ajustando color y subtitulos"

        # 4. Update status to 'descartado'
        res = client.post(
            f"/api/v1/distribution/workflow/{test_video_name}/status",
            json={"status": "descartado", "notes": "Tomas borrosas"}
        )
        assert res.status_code == 200
        assert res.json()["workflow_status"] == "descartado"

        # 5. Clear queue for discarded
        res = client.post(
            "/api/v1/distribution/queue/clear",
            json={"scope": "discarded"}
        )
        assert res.status_code == 200
        assert res.json()["deleted_count"] >= 1

        # File should be deleted
        assert not test_video_path.exists()

        # Queue should no longer have the file
        res = client.get("/api/v1/distribution/queue")
        matching = [v for v in res.json()["ready_videos"] if v["filename"] == test_video_name]
        assert len(matching) == 0

    finally:
        # Cleanup if still exists
        if test_video_path.exists():
            test_video_path.unlink()


def test_delete_single_queue_video():
    settings.OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    temp_file = settings.OUTPUTS_DIR / "test_single_delete.mp4"
    temp_file.write_bytes(b"test")

    try:
        assert temp_file.exists()
        res = client.delete(f"/api/v1/distribution/queue/{temp_file.name}")
        assert res.status_code == 200
        assert not temp_file.exists()
    finally:
        if temp_file.exists():
            temp_file.unlink()
