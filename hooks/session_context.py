"""SessionStart: brief the model on the current Tutu project (only if .tutu/ exists)."""

from _bootstrap import emit, read_event

from tutu_runtime import budget, config, provenance
from tutu_runtime.setup import sync_aris_reviewer
from tutu_runtime.paths import find_project_root, project_dir


def main() -> None:
    ev = read_event()
    root = find_project_root(ev.get("cwd"))
    if root is None:
        return
    sync_aris_reviewer(root, log=lambda *_: None)
    cfg = config.load(root)
    pdir = project_dir(root)
    plans = sorted((pdir / "plans").glob("*.md"))
    pending = pdir / "approvals" / "pending.md"
    n_pending = pending.read_text(encoding="utf-8").count("\n## ") if pending.is_file() else 0
    runs = provenance.list_runs(root)
    b = budget.summary(root)
    lines = [
        f"[Tutu] Project '{config.get(cfg, 'project.name', root.name)}' at {root}",
        f"- data sensitivity: {config.get(cfg, 'data.sensitivity')}; protected (read-only): "
        f"{', '.join(config.get(cfg, 'data.protected_paths', []) or []) or 'none'}",
        f"- reviewer backend: {config.get(cfg, 'reviewer.backend')}; device pref: {config.get(cfg, 'compute.device')}",
        f"- latest plan: {plans[-1].relative_to(root).as_posix() if plans else 'none'}; runs: {len(runs)}; "
        f"pending approvals: {n_pending}",
        f"- budget used: ${b['usd']['used']} of ${b['usd']['cap']} per session cap",
        "- Use /tutu:tutu <goal> to orchestrate. Evidence labels [Source]/[Inference]/[Hypothesis] are mandatory "
        "in scientific claims; every reported number needs a run_id from `tutu provenance capture`.",
    ]
    if n_pending:
        lines.append(f"- ATTENTION: {n_pending} action(s) await approval in .tutu/approvals/pending.md")
    emit({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "\n".join(lines)}})


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import sys
        print(f"tutu session_context error: {e}", file=sys.stderr)
