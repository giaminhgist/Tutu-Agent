"""Cross-platform locations used by Tutu."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_DIR = ".tutu"


def plugin_root() -> Path:
    """Root of the Tutu-Agent repo / installed plugin (runtime/tutu_runtime/paths.py -> ../..)."""
    env = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env and (Path(env) / "runtime" / "tutu_runtime").is_dir():
        return Path(env)
    return Path(__file__).resolve().parents[2]


def tutu_home() -> Path:
    """User-level Tutu directory (~/.tutu, overridable with TUTU_HOME)."""
    return Path(os.environ.get("TUTU_HOME") or Path.home() / ".tutu").expanduser()


def expand(p: str | os.PathLike) -> Path:
    return Path(os.path.expandvars(str(p))).expanduser()


def find_project_root(start: str | os.PathLike | None = None) -> Path | None:
    """Nearest ancestor (inclusive) containing a .tutu/ directory, else None.

    Tutu is opt-in per project: hooks and memory do nothing outside such a root.
    The user's home directory is never treated as a project (~/.tutu is the global store).
    """
    here = Path(start or os.getcwd()).resolve()
    home = Path.home().resolve()
    for d in (here, *here.parents):
        if d == home:
            return None
        if (d / PROJECT_DIR).is_dir():
            return d
    return None


def project_dir(root: Path) -> Path:
    return root / PROJECT_DIR


def is_within(path: str | os.PathLike, parent: str | os.PathLike) -> bool:
    """Case-insensitive on Windows, symlink-resolved containment check."""
    a = os.path.normcase(str(Path(path).resolve()))
    b = os.path.normcase(str(Path(parent).resolve()))
    return a == b or a.startswith(b.rstrip("\\/") + os.sep)
