import pytest
from pathlib import Path
from app.services.broll_manager import LocalBrollManager
from app.config import settings


def test_broll_manager_tagging_and_selection(tmp_path):
    manager = LocalBrollManager(library_dir=tmp_path)

    # Create dummy vertical asset files
    tech_file = tmp_path / "coding_python_dark_916.mp4"
    tech_file.write_text("dummy")

    finance_file = tmp_path / "finance_crypto_chart_vertical.mp4"
    finance_file.write_text("dummy")

    assets = manager.index_library()
    assert len(assets) == 2

    # Query for coding topic
    selected = manager.select_broll_for_cue("python machine learning coding")
    assert selected is not None
    assert "coding" in selected.tags or "coding" in selected.name
