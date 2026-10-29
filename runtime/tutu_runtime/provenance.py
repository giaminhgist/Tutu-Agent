"""Reproducibility manifests: every result links back to code, data, config, seeds and environment.

    capture()  -> .tutu/runs/<run_id>/manifest.json   (call BEFORE launching a run)
    finalize() -> adds status, result-file hashes, metrics (call AFTER the run)

A result without a run_id is not allowed into a paper (enforced by the reviewer agent
via aris:paper-claim-audit).
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from . import device as device_mod
from . import trace
from .paths import project_dir

# Hashing whole datasets can be slow; above this many bytes per file we hash
# (size, mtime, first+last 1 MiB) instead and mark the entry as "fast".
FULL_HASH_LIMIT = 256 * 1024 * 1024
CHUNK = 1024 * 1024


def _run(cmd: list[str], cwd: Path) -> str | None:
    try:
        out = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout if out.returncode == 0 else None


def file_digest(path: Path) -> dict:
    st = path.stat()
    h = hashlib.sha256()
    mode = "full"
    with path.open("rb") as f:
        if st.st_size <= FULL_HASH_LIMIT:
            for block in iter(lambda: f.read(CHUNK), b""):
                h.update(block)
        else:
            mode = "fast"
            h.update(f"{st.st_size}:{int(st.st_mtime)}".encode())
            h.update(f.read(CHUNK))
            f.seek(-CHUNK, os.SEEK_END)
            h.update(f.read(CHUNK))
    return {"sha256": h.hexdigest(), "bytes": st.st_size, "hash_mode": mode}


def path_digest(path: Path, root: Path) -> dict:
    """Digest a file or a directory tree (stable order, relative names included)."""
    rel = os.path.relpath(path, root)
    if path.is_file():
        return {"path": rel, **file_digest(path)}
    if not path.is_dir():
        return {"path": rel, "missing": True}
    h = hashlib.sha256()
    n = size = 0
    mode = "full"
    for p in sorted(q for q in path.rglob("*") if q.is_file()):
        d = file_digest(p)
        mode = "fast" if d["hash_mode"] == "fast" else mode
        h.update(p.relative_to(path).as_posix().encode() + b"\0" + d["sha256"].encode())
        n += 1
        size += d["bytes"]
    return {"path": rel, "sha256": h.hexdigest(), "files": n, "bytes": size, "hash_mode": mode}


def git_state(root: Path, run_dir: Path) -> dict:
    sha = _run(["git", "rev-parse", "HEAD"], root)
    if sha is None:
        return {"available": False}
    status = _run(["git", "status", "--porcelain"], root) or ""
    diff = _run(["git", "diff", "HEAD"], root) or ""
    state = {
        "available": True,
        "commit": sha.strip(),
        "branch": (_run(["git", "rev-parse", "--abbrev-ref", "HEAD"], root) or "").strip(),
        "dirty": bool(status.strip()),
        "untracked": [l[3:] for l in status.splitlines() if l.startswith("??")][:200],
    }
    if diff:
        (run_dir / "git.diff").write_text(diff, encoding="utf-8")
        state["diff_file"] = "git.diff"
        state["diff_sha256"] = hashlib.sha256(diff.encode()).hexdigest()
    return state


def environment() -> dict:
    env = {
        "python": sys.version.split()[0],
        "executable": sys.executable,
        "platform": platform.platform(),
        "os": platform.system(),
        "machine": platform.machine(),
        "conda_env": os.environ.get("CONDA_DEFAULT_ENV"),
        "virtual_env": os.environ.get("VIRTUAL_ENV"),
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
    }
    return env


def pip_freeze(python: str | None = None) -> str:
    exe = python or sys.executable
    try:
        out = subprocess.run([exe, "-m", "pip", "freeze", "--all"], capture_output=True, text=True, timeout=120)
        return out.stdout if out.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _new_run_id(name: str | None) -> str:
    stamp = trace.now().replace(":", "").replace("-", "").replace("+0000", "Z")[:15]
    salt = hashlib.sha1(os.urandom(8)).hexdigest()[:6]
    slug = "".join(c if c.isalnum() or c in "-_" else "-" for c in (name or "run"))[:40].strip("-")
    return f"{stamp}-{slug}-{salt}"


def capture(
    project_root: Path,
    command: str,
    *,
    name: str | None = None,
    configs: list[str] = (),
    data: list[str] = (),
    seeds: list[int] = (),
    python: str | None = None,
    notes: str = "",
    device_pref: str = "auto",
) -> dict:
    run_id = _new_run_id(name)
    run_dir = project_dir(project_root) / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    cfg_entries = []
    for c in configs:
        p = (project_root / c).resolve()
        entry = path_digest(p, project_root)
        if p.is_file():
            snap = run_dir / "configs" / p.name
            snap.parent.mkdir(exist_ok=True)
            shutil.copy2(p, snap)
            entry["snapshot"] = snap.relative_to(run_dir).as_posix()
        cfg_entries.append(entry)

    freeze = pip_freeze(python)
    (run_dir / "requirements.lock.txt").write_text(freeze, encoding="utf-8")

    manifest = {
        "run_id": run_id,
        "created_at": trace.now(),
        "status": "started",
        "command": command,
        "cwd": str(project_root),
        "seeds": list(seeds),
        "notes": notes,
        "git": git_state(project_root, run_dir),
        "configs": cfg_entries,
        "data": [path_digest((project_root / d).resolve(), project_root) for d in data],
        "dvc": _dvc_state(project_root),
        "environment": {**environment(), "pip_freeze_file": "requirements.lock.txt",
                        "pip_freeze_sha256": hashlib.sha256(freeze.encode()).hexdigest()},
        "device": device_mod.detect(device_pref),
        "results": [],
    }
    _write(run_dir, manifest)
    trace.append(project_root, {"type": "run_started", "run_id": run_id, "command": command})
    return manifest


def _dvc_state(root: Path) -> dict | None:
    if not (root / ".dvc").is_dir():
        return None
    return {"lock_sha256": file_digest(root / "dvc.lock")["sha256"]} if (root / "dvc.lock").is_file() else {"present": True}


def finalize(project_root: Path, run_id: str, *, status: str, results: list[str] = (),
             metrics: dict | None = None) -> dict:
    run_dir = project_dir(project_root) / "runs" / run_id
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    manifest["status"] = status
    manifest["finished_at"] = trace.now()
    manifest["results"] = [path_digest((project_root / r).resolve(), project_root) for r in results]
    if metrics:
        manifest["metrics"] = metrics
    _write(run_dir, manifest)
    trace.append(project_root, {"type": "run_finished", "run_id": run_id, "status": status})
    return manifest


def _write(run_dir: Path, manifest: dict) -> None:
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


def list_runs(project_root: Path) -> list[dict]:
    runs_dir = project_dir(project_root) / "runs"
    out = []
    for m in sorted(runs_dir.glob("*/manifest.json")):
        try:
            d = json.loads(m.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        out.append({k: d.get(k) for k in ("run_id", "status", "created_at", "command")})
    return out
