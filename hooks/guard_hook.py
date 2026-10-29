"""PreToolUse: enforce Tutu's human-in-the-loop policy (see runtime/tutu_runtime/guard.py)."""

from _bootstrap import emit, read_event

from tutu_runtime import guard


def main() -> None:
    ev = read_event()
    decision, reason = guard.evaluate(ev.get("tool_name", ""), ev.get("tool_input") or {}, ev.get("cwd"))
    if decision == guard.ALLOW:
        return  # no opinion: normal permission flow applies
    emit({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                 "permissionDecision": decision,
                                 "permissionDecisionReason": reason}})


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # a buggy guard must not brick the session; surface it instead
        import sys
        print(f"tutu guard error: {e}", file=sys.stderr)
