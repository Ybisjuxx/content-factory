import os
import subprocess
import pytest
from pathlib import Path
from app.config import settings
from app.database import create_db_and_tables
from app.pipeline.orchestrator import VideoPipelineOrchestrator
from app.models.job import JobStatus


@pytest.fixture(scope="module")
def sample_raw_video(tmp_path_factory):
    """Generates a small 5-second 1080x1920 test video with audio to test the rendering engine."""
    tmp_dir = tmp_path_factory.mktemp("video_test")
    raw_video = tmp_dir / "test_raw_recording.mp4"
    bg_music = tmp_dir / "test_bg_music.mp3"

    ffmpeg_bin = settings.resolve_ffmpeg_path()

    # 1. Generate 6-second vertical talking head mock video
    cmd_vid = [
        ffmpeg_bin, "-y",
        "-f", "lavfi", "-i", "testsrc=size=1080x1920:rate=30",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=16000",
        "-t", "6",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        str(raw_video)
    ]
    subprocess.run(cmd_vid, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

    # 2. Generate ambient background music track
    cmd_mus = [
        ffmpeg_bin, "-y",
        "-f", "lavfi", "-i", "sine=frequency=220:sample_rate=44100",
        "-t", "8",
        "-c:a", "libmp3lame", "-b:a", "128k",
        str(bg_music)
    ]
    subprocess.run(cmd_mus, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

    return str(raw_video), str(bg_music)


def test_full_pipeline_execution(sample_raw_video, tmp_path):
    raw_video_path, bg_music_path = sample_raw_video
    final_output_path = tmp_path / "final_autonomous_short.mp4"

    create_db_and_tables()
    orchestrator = VideoPipelineOrchestrator()

    options = {
        "enable_broll": True,
        "enable_svg_cards": True,
        "enable_subtitles": True,
        "enable_music_ducking": True,
        "music_track_path": bg_music_path,
    }

    job = orchestrator.run_pipeline(
        job_id="test-e2e-job",
        input_video_path=raw_video_path,
        output_video_path=str(final_output_path),
        options=options
    )

    assert job.status == JobStatus.COMPLETED
    assert job.progress == 100.0
    assert Path(job.output_path).exists()
    assert Path(job.output_path).stat().st_size > 0
