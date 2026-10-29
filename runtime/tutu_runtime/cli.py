"""Command line: `python -m tutu_runtime <command>` (or `tutu <command>` when pip-installed)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import budget, device, kb, provenance, trace
from . import config as config_mod
from . import setup as setup_mod
from .paths import find_project_root, project_dir


def _root(args, required: bool = True) -> Path | None:
    root = find_project_root(getattr(args, "project", None) or ".")
    if root is None and required:
        sys.exit("Not inside a Tutu project (no .tutu/ found). Run `python -m tutu_runtime init` first.")
    return root


def _print(obj) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):  # Windows consoles default to a legacy code page
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(prog="tutu", description="Tutu Agent runtime")
    sub = ap.add_subparsers(dest="command", required=True)

    s = sub.add_parser("setup", help="one-time machine setup (~/.tutu, ARIS wiring, reviewer MCP)")
    s.add_argument("--reviewer", choices=["claude", "codex"])

    s = sub.add_parser("init", help="make the current directory a Tutu project")
    s.add_argument("--project", default=".")
    s.add_argument("--name")

    s = sub.add_parser("doctor", help="check installation")
    s.add_argument("--project", default=".")
    s.add_argument("--skills", action="store_true", help="also verify the orchestrated skill repos and their dependencies")
    s.add_argument("--live", action="store_true", help="with --skills: live round-trip through the claude-review reviewer")

    s = sub.add_parser("deps", help="install skill dependencies (Tutu venv, optional LaTeX / draw.io)")
    s.add_argument("--extras", nargs="*", default=[], help="extra pip packages, e.g. deepxiv-sdk exa-py wandb")
    s.add_argument("--with-latex", action="store_true")
    s.add_argument("--with-drawio", action="store_true")

    s = sub.add_parser("aris-route", help="resolve the ARIS reviewer route for this project")
    s.add_argument("--project", default=".")
    s.add_argument("--tier", choices=["deep", "regular"], default="deep")

    s = sub.add_parser("status", help="plans, runs, approvals, budget for this project")
    s.add_argument("--project", default=".")

    s = sub.add_parser("device", help="show the compute device Tutu will use")

    s = sub.add_parser("provenance", help="reproducibility manifests")
    psub = s.add_subparsers(dest="action", required=True)
    c = psub.add_parser("capture")
    c.add_argument("--cmd", dest="run_cmd", required=True, help="exact command that will be run")
    c.add_argument("--name")
    c.add_argument("--config", action="append", default=[])
    c.add_argument("--data", action="append", default=[])
    c.add_argument("--seed", action="append", type=int, default=[])
    c.add_argument("--python", help="interpreter of the experiment env (for pip freeze)")
    c.add_argument("--notes", default="")
    c.add_argument("--project", default=".")
    f = psub.add_parser("finalize")
    f.add_argument("run_id")
    f.add_argument("--status", required=True, choices=["succeeded", "failed", "killed"])
    f.add_argument("--result", action="append", default=[])
    f.add_argument("--metrics", help="JSON string or path to a JSON file")
    f.add_argument("--project", default=".")
    l = psub.add_parser("list")
    l.add_argument("--project", default=".")

    s = sub.add_parser("kb", help="knowledge base")
    ksub = s.add_subparsers(dest="action", required=True)
    k = ksub.add_parser("search")
    k.add_argument("query")
    k.add_argument("--scope", choices=["all", "project", "global"], default="all")
    k.add_argument("--limit", type=int, default=10)
    k.add_argument("--project", default=".")
    k = ksub.add_parser("add-paper")
    for a in ("title", "year", "keyword"):
        k.add_argument(f"--{a}", required=True)
    k.add_argument("--author", action="append", default=[], help="repeat; first author first")
    for a in ("venue", "doi", "arxiv", "url", "tldr", "bibtex"):
        k.add_argument(f"--{a}", default="")
    k.add_argument("--tag", action="append", default=[])
    k.add_argument("--project", default=".")
    k = ksub.add_parser("promote")
    k.add_argument("path")
    k.add_argument("--approve", action="store_true")
    k.add_argument("--project", default=".")
    k = ksub.add_parser("reindex")
    k.add_argument("--project", default=".")

    s = sub.add_parser("budget", help="record or show spend")
    bsub = s.add_subparsers(dest="action", required=True)
    b = bsub.add_parser("add")
    b.add_argument("kind", choices=sorted(budget.KINDS))
    b.add_argument("amount", type=float)
    b.add_argument("--note", default="")
    b.add_argument("--project", default=".")
    b = bsub.add_parser("show")
    b.add_argument("--project", default=".")
    b = bsub.add_parser("check")
    b.add_argument("kind", choices=sorted(budget.KINDS))
    b.add_argument("amount", type=float)
    b.add_argument("--project", default=".")

    s = sub.add_parser("trace", help="append an event to .tutu/trace.jsonl")
    s.add_argument("type")
    s.add_argument("--data", default="{}", help="JSON object")
    s.add_argument("--project", default=".")

    s = sub.add_parser("run", help="headless Auto Research Loop (Claude Agent SDK)")
    s.add_argument("--goal", required=True)
    s.add_argument("--project", default=".")
    s.add_argument("--budget-usd", type=float)
    s.add_argument("--max-iter", type=int)
    s.add_argument("--max-turns", type=int)
    s.add_argument("--model")
    s.add_argument("--dev-plugin", action="store_true", help="load Tutu from this checkout instead of the installed plugin")
    s.add_argument("--dry-run", action="store_true")

    a = ap.parse_args(argv)

    if a.command == "setup":
        setup_mod.setup_machine(a.reviewer)
    elif a.command == "init":
        root = Path(a.project).resolve()
        setup_mod.init_project(root, a.name)
        print(f"Tutu project ready: {project_dir(root)}")
    elif a.command == "doctor":
        bad = 0
        for name, ok, info in setup_mod.doctor(_root(a, required=False)):
            print(f"[{'ok' if ok else '!!'}] {name}: {info}")
            bad += not ok
        if a.skills:
            from . import skills_check
            print("\n== skills ==")
            for group, item, status, detail in skills_check.run(live=a.live):
                print(f"[{status:8}] {group:8} {item}: {detail}")
                bad += status == "MISSING"
        return 1 if bad else 0
    elif a.command == "deps":
        from . import sysdeps
        sysdeps.create_venv(a.extras)
        if a.with_latex:
            sysdeps.install_latex()
        if a.with_drawio:
            sysdeps.install_drawio()
    elif a.command == "aris-route":
        import subprocess
        from .skills_check import aris_repo
        repo = aris_repo()
        if not repo:
            sys.exit("ARIS repo not resolved (~/.aris/repo); run `tutu setup`.")
        root = _root(a, required=False) or Path(a.project).resolve()
        r = subprocess.run([sys.executable, str(repo / "tools" / "reviewer_route.py"), "--project", str(root),
                            "--host", "claude-code", "--tier", a.tier], capture_output=True, text=True)
        print(r.stdout.strip() or r.stderr.strip())
        return r.returncode
    elif a.command == "device":
        _print(device.detect(config_mod.get(config_mod.load(_root(a, required=False)), "compute.device", "auto")))
    elif a.command == "status":
        root = _root(a)
        pdir = project_dir(root)
        pending = pdir / "approvals" / "pending.md"
        _print({
            "project": str(root),
            "plans": sorted(p.name for p in (pdir / "plans").glob("*.md"))[-5:],
            "runs": provenance.list_runs(root)[-10:],
            "reviews": sorted(p.name for p in (pdir / "reviews").glob("*"))[-5:],
            "pending_approvals": pending.read_text(encoding="utf-8").count("\n## ") if pending.is_file() else 0,
            "budget": budget.summary(root),
            "recent_trace": trace.read(root, last=5),
        })
    elif a.command == "provenance":
        root = _root(a)
        if a.action == "capture":
            m = provenance.capture(root, a.run_cmd, name=a.name,
                                   configs=a.config, data=a.data, seeds=a.seed, python=a.python, notes=a.notes,
                                   device_pref=config_mod.get(config_mod.load(root), "compute.device", "auto"))
            _print({"run_id": m["run_id"], "manifest": str(project_dir(root) / "runs" / m["run_id"] / "manifest.json"),
                     "device": m["device"]["device"], "git_dirty": m["git"].get("dirty")})
        elif a.action == "finalize":
            metrics = None
            if a.metrics:
                p = Path(a.metrics)
                metrics = json.loads(p.read_text(encoding="utf-8") if p.is_file() else a.metrics)
            m = provenance.finalize(root, a.run_id, status=a.status, results=a.result, metrics=metrics)
            _print({"run_id": m["run_id"], "status": m["status"], "results": len(m["results"])})
        else:
            _print(provenance.list_runs(root))
    elif a.command == "kb":
        root = _root(a, required=False)
        if a.action == "search":
            _print(kb.search(a.query, a.scope, root, a.limit))
        elif a.action == "add-paper":
            page = kb.add_paper(title=a.title, authors=a.author, year=a.year, keyword=a.keyword, venue=a.venue,
                                doi=a.doi, arxiv=a.arxiv, url=a.url, tags=a.tag, tldr=a.tldr or "TODO",
                                project_root=root, bibtex=a.bibtex)
            print(page)
        elif a.action == "promote":
            print(kb.promote(_root(a), a.path, approved=a.approve))
        else:
            n = kb.index("global", None)
            if root:
                n += kb.index("project", root)
            print(f"indexed {n} changed documents")
    elif a.command == "budget":
        root = _root(a)
        if a.action == "add":
            budget.record(root, a.kind, a.amount, a.note)
        elif a.action == "check":
            over = budget.would_exceed(root, a.kind, a.amount)
            print("EXCEEDS_CAP" if over else "OK")
            return 2 if over else 0
        _print(budget.summary(root))
    elif a.command == "trace":
        trace.append(_root(a), {"type": a.type, **json.loads(a.data)})
    elif a.command == "run":
        from . import sdk_runner
        _print(sdk_runner.run(a.goal, a.project, budget_usd=a.budget_usd, max_iter=a.max_iter,
                              max_turns=a.max_turns, model=a.model, dev_plugin=a.dev_plugin, dry_run=a.dry_run))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
