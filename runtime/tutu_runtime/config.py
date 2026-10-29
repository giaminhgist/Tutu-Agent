"""Layered configuration: repo defaults < ~/.tutu/config.toml < <project>/.tutu/project.toml."""

from __future__ import annotations

import copy
import tomllib
from pathlib import Path
from typing import Any

from .paths import plugin_root, project_dir, tutu_home


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    with path.open("rb") as f:
        return tomllib.load(f)


def _merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load(project_root: Path | None = None) -> dict[str, Any]:
    cfg = _load(plugin_root() / "config" / "tutu.default.toml")
    cfg = _merge(cfg, _load(tutu_home() / "config.toml"))
    if project_root is not None:
        cfg = _merge(cfg, _load(project_dir(project_root) / "project.toml"))
    return cfg


def get(cfg: dict, dotted: str, default: Any = None) -> Any:
    cur: Any = cfg
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur
