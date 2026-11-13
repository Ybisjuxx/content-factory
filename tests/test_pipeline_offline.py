"""End-to-end pipeline run with a stubbed transcriber (no Whisper/Ollama needed).

Covers jump-cut assembly, overlays, subtitles and the A/V-sync regression.
"""
import json
import shutil
import subprocess

import pytest

from app.config import settings
from app.database import create_db_and_tables
from app.models.job import JobStatus
from app.pipeline.orchestrator import VideoPipelineOrchestrator

FAKE_TRANSCRIPT = {
    "language": "es", "language_probability": 1.0, "duration": 6.0, "full_text": "uno dos tres",
    "segments": [
        {"id": i, "start": s, "end": e, "text": t,
         "words": [{"word": t, "start": s, "end": e, "probability": 1.0}]}
        for i, (s, e, t) in enumerate([(0.0, 1.8, "uno"), (2.0, 3.8, "dos"), (4.0, 5.8, "tres")])
    ],
}


def _duration(path, stream):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", stream, "-show_entries", "stream=duration", "-of", "json", path],
        capture_output=True, text=True,
    ).stdout
    return float(json.loads(out)["streams"][0]["duration"])


@pytest.fixture
def raw_video(tmp_path):
    out = settings.UPLOADS_DIR / "raw_offline.mp4"
    subprocess.run([
        settings.resolve_ffmpeg_path(), "-y", "-loglevel", "error",
        "-f", "lavfi", "-i", "testsrc=size=270x480:rate=30", "-f", "lavfi", "-i", "sine=f=440:sample_rate=48000",
        "-t", "6", "-c:v", "libx264", "-c:a", "aac", "-shortest", str(out),
    ], check=True)
    return out


@pytest.mark.skipif(shutil.which("ffprobe") is None, reason="ffprobe missing")
def test_pipeline_runs_offline_and_keeps_av_sync(raw_video, monkeypatch):
    create_db_and_tables()
    orch = VideoPipelineOrchestrator()
    monkeypatch.setattr(orch.transcriber, "transcribe", lambda *a, **k: FAKE_TRANSCRIPT)
    monkeypatch.setattr(orch.director, "check_ollama_status", lambda: {"available": False})
    monkeypatch.setattr(settings, "OLLAMA_BASE_URL", "http://127.0.0.1:9")  # force heuristic director

    job = orch.run_pipeline("offline-job", str(raw_video), options={
        "enable_broll": False, "enable_svg_cards": True, "enable_subtitles": True, "enable_music_ducking": False,
    })
    assert job.status == JobStatus.COMPLETED, job.error_message
    v, a = _duration(job.output_path, "v:0"), _duration(job.output_path, "a:0")
    assert abs(v - a) < 0.05, f"A/V drift {v - a:.3f}s"
