"""Cost ledger: API dollars, GPU hours, loop iterations. <project>/.tutu/budget.jsonl"""

from __future__ import annotations

import json
from pathlib import Path

from . import config as config_mod
from . import trace
from .paths import project_dir

KINDS = {"usd": "budget.max_usd_per_session", "gpu_hours": "budget.max_gpu_hours_per_run",
         "loop_iterations": "budget.max_loop_iterations"}


def record(project_root: Path, kind: str, amount: float, note: str = "", session: str = "") -> None:
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {sorted(KINDS)}")
    path = project_dir(project_root) / "budget.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": trace.now(), "kind": kind, "amount": amount, "note": note, "session": session}) + "\n")


def totals(project_root: Path, session: str | None = None) -> dict[str, float]:
    path = project_dir(project_root) / "budget.jsonl"
    out = {k: 0.0 for k in KINDS}
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if session is None or r.get("session") == session:
                out[r["kind"]] = out.get(r["kind"], 0.0) + float(r["amount"])
    return out


def summary(project_root: Path, session: str | None = None) -> dict:
    cfg = config_mod.load(project_root)
    used = totals(project_root, session)
    return {k: {"used": round(used[k], 4), "cap": config_mod.get(cfg, key)} for k, key in KINDS.items()}


def would_exceed(project_root: Path, kind: str, amount: float, session: str | None = None) -> bool:
    cap = config_mod.get(config_mod.load(project_root), KINDS[kind])
    if cap is None:
        return False
    if kind == "gpu_hours":  # per-run cap, not cumulative
        return amount > float(cap)
    return totals(project_root, session)[kind] + amount > float(cap)
