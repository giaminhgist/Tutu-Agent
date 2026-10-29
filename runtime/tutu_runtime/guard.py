"""Human-in-the-loop policy. Shared by the PreToolUse hook and the SDK runner's can_use_tool.

evaluate() returns ("allow" | "ask" | "deny", reason). "allow" means "Tutu has no
objection": the normal Claude Code permission flow still applies.

Only active inside a Tutu project (a directory tree with .tutu/). Elsewhere it is a no-op,
so installing Tutu globally never changes behaviour in unrelated projects.
"""

from __future__ import annotations

import os
import re
import shlex
from pathlib import Path

from . import config as config_mod
from .paths import find_project_root, is_within, project_dir

ALLOW, ASK, DENY = "allow", "ask", "deny"

WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
READ_TOOLS = {"Read", "Grep", "Glob"}

# Shell verbs that modify every path they are given.
MUTATING = re.compile(
    r"^\s*(?:sudo\s+)?(rm|rmdir|mv|truncate|shred|unlink|chmod|chown|touch|mkdir|tee|"
    r"sed\s+-i|perl\s+-i|git\s+rm|git\s+mv|git\s+clean|git\s+checkout\s+--|Remove-Item|Move-Item|"
    r"Set-Content|Out-File|del|erase|rd|move)(?=\s|$)",
    re.I,
)
# Copy-like verbs only modify their LAST path argument (the destination).
COPYING = re.compile(r"^\s*(?:sudo\s+)?(cp|rsync|ln|Copy-Item|copy|xcopy|robocopy|dd)(?=\s|$)", re.I)
SEGMENT_SPLIT = re.compile(r"\s*(?:&&|\|\||;|\||\n)\s*")
REDIRECT = re.compile(r"(?<![0-9&])>{1,2}\s*([^\s;&|]+)")
RM_RF = re.compile(r"(?:^|[\s;&|(])rm\s+(?:-[a-zA-Z]*[rR][a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*[rR]|-r\s+-f|-f\s+-r|--recursive)\b", re.I)

ASK_PATTERNS = [
    (re.compile(r"\bgit\s+push\b"), "git push publishes commits to a remote"),
    (re.compile(r"\bgit\s+(?:reset\s+--hard|push\s+.*--force|branch\s+-D)\b"), "destructive git operation"),
    (re.compile(r"\bgh\s+(?:pr\s+(?:create|merge)|release\s+create|repo\s+create)\b"), "GitHub publication"),
    (re.compile(r"\b(?:arxiv|openreview)\b.*\b(?:submit|upload)\b", re.I), "paper submission"),
    (re.compile(r"\boverleaf[-_ ]sync\b.*\bpush\b", re.I), "pushes the manuscript to Overleaf"),
    (re.compile(r"\btwine\s+upload\b|\b(?:npm|cargo|poetry|uv)\s+publish\b|\bhuggingface-cli\s+upload\b|\bhf\s+upload\b"),
     "publishes a package/model"),
    (re.compile(r"\bvastai\s+(?:create|launch)\b|\bmodal\s+(?:run|deploy)\b"), "rents cloud GPU (costs money)"),
    (re.compile(r"\bsbatch\b|\bqsub\b"), "submits a cluster GPU job"),
    (re.compile(r"\bcurl\b.*\s-(?:X\s*POST|d|F)\b|\bscp\b.*\S+@\S+:|\brsync\b.*\S+@\S+:", re.I), "sends data off this machine"),
]


def _tokens(cmd: str) -> list[str]:
    try:
        return shlex.split(cmd, posix=os.name != "nt")
    except ValueError:
        return cmd.split()


def _resolve(p: str, cwd: Path) -> Path:
    p = os.path.expandvars(os.path.expanduser(p.strip("'\"")))
    q = Path(p)
    return q if q.is_absolute() else (cwd / q)


def _paths_in(cmd: str, cwd: Path) -> list[Path]:
    out = []
    for t in _tokens(cmd):
        if t.startswith("-") or not t or "://" in t:
            continue
        for piece in re.split(r"[=,]", t):
            if piece and re.search(r"[\\/.~]|^\w", piece):
                out.append(_resolve(piece, cwd))
    return out


def _protected(cfg: dict, root: Path) -> list[Path]:
    return [_resolve(p, root) for p in config_mod.get(cfg, "data.protected_paths", []) or []]


def _sensitive(cfg: dict, root: Path) -> list[Path]:
    if config_mod.get(cfg, "data.sensitivity") != "phi":
        return []
    return [_resolve(p, root) for p in config_mod.get(cfg, "data.sensitive_paths", []) or []]


def _phi_approved(root: Path) -> bool:
    return (project_dir(root) / "approvals" / "phi-access.approved").is_file()


def _hits(paths: list[Path], zones: list[Path]) -> Path | None:
    for p in paths:
        for z in zones:
            if is_within(p, z):
                return z
    return None


def evaluate(tool_name: str, tool_input: dict, cwd: str | os.PathLike | None = None) -> tuple[str, str]:
    cwd = Path(cwd or os.getcwd())
    root = find_project_root(cwd)
    if root is None:
        return ALLOW, "not a Tutu project"
    cfg = config_mod.load(root)
    protected = _protected(cfg, root)
    sensitive = _sensitive(cfg, root)

    if tool_name in WRITE_TOOLS:
        target = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
        z = _hits([_resolve(target, cwd)], protected) if target else None
        if z:
            return DENY, f"Tutu: {z} is protected raw data (data.protected_paths). Write derived data elsewhere."
        return ALLOW, ""

    if tool_name in READ_TOOLS:
        target = tool_input.get("file_path") or tool_input.get("path") or ""
        if sensitive and target and _hits([_resolve(target, cwd)], sensitive) and not _phi_approved(root):
            return ASK, ("Tutu: reading PHI-sensitive data. Approve only if this use is covered by the IRB/DUA; "
                         "to approve for the whole project create .tutu/approvals/phi-access.approved")
        return ALLOW, ""

    if tool_name != "Bash":
        return ALLOW, ""

    cmd = tool_input.get("command", "") or ""
    paths = _paths_in(cmd, cwd)

    if RM_RF.search(cmd):
        for p in paths:
            if not is_within(p, root) or p.resolve() == root.resolve():
                return DENY, f"Tutu: recursive delete outside (or of) the project root: {p}"
        if any(t in ("*", "/", "~", "..") for t in _tokens(cmd)):
            return DENY, "Tutu: recursive delete with a broad target"

    for seg in SEGMENT_SPLIT.split(cmd):
        written: list[Path] = [_resolve(m, cwd) for m in REDIRECT.findall(seg)]
        seg_paths = _paths_in(REDIRECT.sub(" ", seg), cwd)
        if MUTATING.search(seg):
            written += seg_paths
        elif COPYING.search(seg):
            dd_out = re.search(r"\bof=(\S+)", seg)
            written += [_resolve(dd_out.group(1), cwd)] if dd_out else seg_paths[-1:]
        z = _hits(written, protected)
        if z:
            return DENY, f"Tutu: command would modify protected raw data under {z}"

    if sensitive and _hits(paths, sensitive) and not _phi_approved(root):
        return ASK, "Tutu: command touches PHI-sensitive data (see .tutu/project.toml [data])"

    for pat, why in ASK_PATTERNS:
        if pat.search(cmd):
            return ASK, f"Tutu approval needed: {why}"

    return ALLOW, ""
