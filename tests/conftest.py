"""Test isolation: every run gets its own storage dir and SQLite DB.

Before, the suite wrote jobs, renders and the database into the real storage/
folder of the working copy. Must run before any ``app`` import (pytest loads
conftest first).
"""
import importlib.util
import json
import os
import tempfile
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
_TMP_STORAGE = Path(tempfile.mkdtemp(prefix="cf_test_storage_"))

os.environ["STORAGE_DIR"] = str(_TMP_STORAGE)
# Sample clips shipped in the repo stay readable by the API under test.
os.environ["ALLOWED_MEDIA_DIRS"] = json.dumps([str(_REPO / "storage" / "broll_library"), tempfile.gettempdir()])
os.environ["ALLOWED_HOSTS"] = json.dumps(["testserver", "127.0.0.1", "localhost"])
os.environ["TRENDS_LIVE_FETCH_ENABLED"] = "false"

HAS_WHISPER = importlib.util.find_spec("faster_whisper") is not None
requires_whisper = pytest.mark.skipif(not HAS_WHISPER, reason="faster-whisper no instalado")
