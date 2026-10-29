"""Append-only audit trail: <project>/.tutu/trace.jsonl."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .paths import project_dir


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def append(project_root: Path, event: dict) -> None:
    path = project_dir(project_root) / "trace.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    rec = {"ts": now(), **event}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def read(project_root: Path, last: int | None = None) -> list[dict]:
    path = project_dir(project_root) / "trace.jsonl"
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    if last:
        lines = lines[-last:]
    out = []
    for l in lines:
        try:
            out.append(json.loads(l))
        except json.JSONDecodeError:
            continue
    return out
