import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_trends_topics_endpoint():
    res = client.get("/api/v1/trends/topics")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert "title" in data[0]
    assert "platform" in data[0]
    assert "heat_score" in data[0]


def test_trends_ideas_generation():
    res = client.post(
        "/api/v1/trends/ideas",
        json={"niche": "Tecnología & IA", "topic": "herramientas secretas"}
    )
    assert res.status_code == 200
    ideas = res.json()
    assert isinstance(ideas, list)
    assert len(ideas) >= 1
    assert "hook" in ideas[0]
    assert "title" in ideas[0]


def test_distribution_channels():
    res = client.get("/api/v1/distribution/channels")
    assert res.status_code == 200
    channels = res.json()
    assert len(channels) >= 2


def test_distribution_queue():
    res = client.get("/api/v1/distribution/queue")
    assert res.status_code == 200
    data = res.json()
    assert "ready_videos" in data
    assert "history" in data


def test_generator_short_script():
    res = client.post(
        "/api/v1/generator/create",
        json={"subject": "Inteligencia artificial en 2026"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "script" in data
