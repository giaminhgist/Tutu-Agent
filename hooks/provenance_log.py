"""PostToolUse(Bash): trace experiment launches and nudge when no provenance manifest exists."""

import re
import time

from _bootstrap import emit, read_event

from tutu_runtime import trace
from tutu_runtime.paths import find_project_root, project_dir

EXPERIMENT = re.compile(
    r"\b(?:python[\d.]*|py)\s+(?:-m\s+)?\S*(?:train|finetune|fine_tune|pretrain|eval|evaluate|experiment|sweep|run_exp)\S*"
    r"|\btorchrun\b|\baccelerate\s+launch\b|\bdeepspeed\b|\bsbatch\b|\bmodal\s+run\b",
    re.I,
)
RECENT_SECONDS = 6 * 3600


def main() -> None:
    ev = read_event()
    cmd = (ev.get("tool_input") or {}).get("command", "")
    if not cmd or "tutu_runtime" in cmd or not EXPERIMENT.search(cmd):
        return
    root = find_project_root(ev.get("cwd"))
    if root is None:
        return
    trace.append(root, {"type": "experiment_command", "command": cmd[:2000],
                        "session": ev.get("session_id"), "agent": ev.get("agent_type")})
    runs = list((project_dir(root) / "runs").glob("*/manifest.json"))
    fresh = any(time.time() - m.stat().st_mtime < RECENT_SECONDS for m in runs)
    if not fresh:
        emit({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext":
              "[Tutu] This looks like an experiment run but no provenance manifest was captured in the last 6h. "
              "Results from it cannot be cited. Capture one now: tutu provenance capture "
              "--cmd \"<exact command>\" --config <cfg> --data <data dir> --seed <seed>"}})


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import sys
        print(f"tutu provenance_log error: {e}", file=sys.stderr)
