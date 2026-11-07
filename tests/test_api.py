import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import create_db_and_tables
from app.config import settings

settings.ensure_directories()
create_db_and_tables()

client = TestClient(app)


def test_system_health():
    res = client.get("/api/v1/system/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_system_status():
    res = client.get("/api/v1/system/status")
    assert res.status_code == 200
    data = res.json()
    assert "ollama" in data
    assert "faster_whisper" in data
    assert "ffmpeg" in data


def test_svg_generation_endpoint():
    res = client.post(
        "/api/v1/assets/svg/generate",
        json={
            "card_type": "stat",
            "title": "100% LOCAL",
            "content": "Zero cloud lock-in",
            "badge": "PRIVACY"
        }
    )
    assert res.status_code == 200
    assert "file_path" in res.json()


def test_list_jobs():
    res = client.get("/api/v1/jobs")
    assert res.status_code == 200
    assert isinstance(res.json(), list)
