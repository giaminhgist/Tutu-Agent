#!/usr/bin/env python3
"""Install Tutu Agent for the current user (Linux, macOS, Windows).

    git clone https://github.com/giaminhgist/Tutu-Agent && cd Tutu-Agent
    python install.py                      # use this checkout as the marketplace (git pull = update)
    python install.py --github giaminhgist/Tutu-Agent   # or install from GitHub without a checkout
    python install.py --reviewer codex     # cross-model reviewer (needs Codex CLI, then /aris:setup)
    python install.py --with-latex --with-drawio --extras deepxiv-sdk exa-py wandb   # everything

Idempotent: re-running only fills in what is missing.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MARKETPLACE = "tutu"
PLUGINS = ["superpowers", "aris", "humanizer", "supervisor-skills", "tutu"]


def sh(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    print("$", " ".join(args), flush=True)
    r = subprocess.run(args, text=True, capture_output=True)
    out = (r.stdout + r.stderr).strip()
    if out:
        print("  " + out.replace("\n", "\n  "))
    if check and r.returncode != 0:
        sys.exit(f"command failed ({r.returncode})")
    return r


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--github", help="owner/repo of Tutu-Agent; default: this checkout")
    ap.add_argument("--reviewer", choices=["claude", "codex"], help="reviewer backend (default: claude)")
    ap.add_argument("--scope", default="user", choices=["user", "project", "local"])
    ap.add_argument("--with-latex", action="store_true", help="install LaTeX (TeX Live / MiKTeX / MacTeX)")
    ap.add_argument("--with-drawio", action="store_true", help="install draw.io desktop (+ xvfb on Linux)")
    ap.add_argument("--extras", nargs="*", default=[], help="extra pip packages for the Tutu venv")
    a = ap.parse_args()

    if sys.version_info < (3, 11):
        sys.exit(f"Python >= 3.11 required (found {sys.version.split()[0]})")
    claude = shutil.which("claude")
    if not claude:
        sys.exit("Claude Code CLI not found on PATH. Install it first: https://code.claude.com/docs")

    source = a.github or str(HERE)
    existing = sh([claude, "plugin", "marketplace", "list"], check=False).stdout
    if MARKETPLACE not in existing.split():
        sh([claude, "plugin", "marketplace", "add", source])
    else:
        sh([claude, "plugin", "marketplace", "update", MARKETPLACE], check=False)

    installed = sh([claude, "plugin", "list"], check=False).stdout
    for p in PLUGINS:
        if f"{p}@{MARKETPLACE}" in installed:
            print(f"  {p}@{MARKETPLACE} already installed")
            continue
        sh([claude, "plugin", "install", f"{p}@{MARKETPLACE}", "--scope", a.scope])

    # Machine setup through the runtime of the installed (or local) copy.
    env = dict(os.environ, PYTHONPATH=str(HERE / "runtime"))
    setup = [sys.executable, "-m", "tutu_runtime", "setup"] + (["--reviewer", a.reviewer] if a.reviewer else [])
    print("$", " ".join(setup))
    subprocess.run(setup, env=env, check=False)
    deps = [sys.executable, "-m", "tutu_runtime", "deps", "--extras", *a.extras]
    deps += ["--with-latex"] if a.with_latex else []
    deps += ["--with-drawio"] if a.with_drawio else []
    print("$", " ".join(deps))
    subprocess.run(deps, env=env, check=False)
    print("\n== doctor ==")
    subprocess.run([sys.executable, "-m", "tutu_runtime", "doctor", "--skills"], env=env, check=False)

    print("""
Done. Next:
  1. Restart Claude Code (MCP servers and plugins load at startup).
  2. In any project:  /tutu:tutu-init   then   /tutu:tutu <your research goal>
  3. Optional headless runner:  pip install claude-agent-sdk   then   tutu run --goal "..." --budget-usd 5
""")
    if a.reviewer == "codex":
        print("  Codex reviewer: install Codex CLI (npm i -g @openai/codex && codex login), then run /aris:setup once.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
