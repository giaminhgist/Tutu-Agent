import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "runtime"))


@pytest.fixture
def home(tmp_path, monkeypatch):
    """Isolated HOME + TUTU_HOME so tests never touch the real user config."""
    h = tmp_path / "home"
    h.mkdir()
    monkeypatch.setenv("HOME", str(h))
    monkeypatch.setenv("USERPROFILE", str(h))  # Windows
    monkeypatch.setenv("TUTU_HOME", str(h / ".tutu"))
    monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)
    return h


@pytest.fixture
def project(home, tmp_path):
    """A Tutu project with protected raw data and PHI settings."""
    root = tmp_path / "work" / "proj"
    (root / ".tutu" / "approvals").mkdir(parents=True)
    (root / "data" / "raw").mkdir(parents=True)
    (root / "data" / "raw" / "s01.tsv").write_text("t,x,y\n0,1,2\n")
    (root / "data" / "phi").mkdir(parents=True)
    (root / ".tutu" / "project.toml").write_text(
        '[project]\nname = "demo"\n'
        '[data]\nprotected_paths = ["data/raw"]\nsensitivity = "phi"\nsensitive_paths = ["data/phi"]\n'
        '[knowledge]\nkb_share = false\n'
        '[budget]\nmax_gpu_hours_per_run = 2.0\nmax_usd_per_session = 1.0\n'
    )
    return root
