"""
Shared fixtures. Adds src/ to the import path and stubs the heavy ML modules
(torch, stable_whisper) when they are not installed, so the suite runs in a
lightweight environment; with the real packages installed the stubs are unused.
"""

import sys
import types
from pathlib import Path

import pytest

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

try:
    import torch  # noqa: F401
except ImportError:
    torch_stub = types.ModuleType("torch")
    torch_stub.cuda = types.SimpleNamespace(is_available=lambda: False)
    torch_stub.float16 = torch_stub.float32 = None
    sys.modules["torch"] = torch_stub

try:
    import stable_whisper  # noqa: F401
except ImportError:
    whisper_stub = types.ModuleType("stable_whisper")

    def _no_model(*args, **kwargs):
        raise RuntimeError("stable_whisper stubbed out in tests")

    whisper_stub.load_model = _no_model
    sys.modules["stable_whisper"] = whisper_stub


@pytest.fixture
def client(tmp_path, monkeypatch):
    """TestClient with the app's DB redirected to a temp file."""
    from fastapi.testclient import TestClient

    import db
    import main

    monkeypatch.setattr(main, "DB", db.transcriptionsDB(str(tmp_path / "test.db")))
    return TestClient(main.app)
