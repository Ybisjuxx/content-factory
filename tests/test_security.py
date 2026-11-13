"""Regression tests for the audit findings (path confinement, XSS, SSRF, CORS, exposure)."""
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.config import settings
from app.database import create_db_and_tables
from app.main import app
from app.security import (
    escape_markup_params,
    resolve_media_path,
    safe_filename,
    sanitize_hex_color,
    validate_webhook_url,
)
from app.services.svg_generator import ProceduralSvgGenerator

settings.ensure_directories()
create_db_and_tables()
client = TestClient(app)


def test_media_path_outside_roots_is_rejected():
    with pytest.raises(HTTPException) as exc:
        resolve_media_path("/etc/passwd")
    assert exc.value.status_code == 403


def test_media_path_traversal_by_name_is_rejected():
    with pytest.raises(HTTPException):
        resolve_media_path("../../app/main.py")


def test_media_path_inside_uploads_is_accepted():
    f = settings.UPLOADS_DIR / "clip.mp4"
    f.write_bytes(b"0")
    assert resolve_media_path("clip.mp4") == f.resolve()


def test_job_with_arbitrary_input_path_is_rejected():
    res = client.post("/api/v1/jobs", json={"input_video_path": "/etc/passwd"})
    assert res.status_code == 403


def test_job_with_external_webhook_is_rejected():
    f = settings.UPLOADS_DIR / "clip2.mp4"
    f.write_bytes(b"0")
    res = client.post("/api/v1/jobs", json={
        "input_video_path": str(f), "n8n_webhook_url": "http://169.254.169.254/latest/meta-data",
    })
    assert res.status_code == 400


@pytest.mark.parametrize("url", ["http://localhost:5678/webhook/x", "http://127.0.0.1:5678/a"])
def test_loopback_webhooks_allowed(url):
    assert validate_webhook_url(url) == url


@pytest.mark.parametrize("url", ["file:///etc/passwd", "http://example.com/hook", "gopher://localhost"])
def test_non_local_webhooks_blocked(url):
    with pytest.raises(HTTPException):
        validate_webhook_url(url)


def test_hex_color_sanitizer_blocks_filter_injection():
    assert sanitize_hex_color("#fff:t=fill[x];movie=/etc/passwd") == "#38BDF8"
    assert sanitize_hex_color("10B981") == "#10B981"


def test_markup_params_are_escaped():
    out = escape_markup_params({"title": "<script>alert(1)</script>", "accent_color": "red\" onload=\"x"})
    assert "<script>" not in out["title"]
    assert out["accent_color"] == "#38BDF8"


def test_svg_card_escapes_text_and_keeps_body():
    path = ProceduralSvgGenerator().generate_card("takeaway", "<script>x</script>", "Cuerpo & visible", "B")
    svg = open(path, encoding="utf-8").read()
    assert "<script>" not in svg
    assert "foreignObject" not in svg  # librsvg/FFmpeg can't render it
    assert "Cuerpo &amp; visible" in svg


def test_database_and_state_files_not_served():
    assert client.get("/storage/content_factory.db").status_code == 404
    assert client.get("/storage/video_workflow.json").status_code == 404


def test_cors_rejects_foreign_origin():
    res = client.options("/api/v1/jobs", headers={
        "Origin": "https://evil.example", "Access-Control-Request-Method": "POST",
    })
    assert res.headers.get("access-control-allow-origin") != "https://evil.example"


def test_safe_filename():
    assert safe_filename("../../a b';.mp4") == "a_b__.mp4"
