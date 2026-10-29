"""Machine setup (once per machine), project init (once per project) and `doctor`."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from . import config as config_mod
from . import device
from .paths import plugin_root, project_dir, tutu_home

REQUIRED_PLUGINS = ["tutu", "superpowers", "aris", "humanizer", "supervisor-skills"]
PROJECT_SUBDIRS = ["plans", "runs", "reviews", "approvals", "artifacts", "notes"]


def _claude() -> str | None:
    return shutil.which("claude")


def installed_plugins() -> dict[str, str]:
    """{plugin_name: install_path} from Claude Code's user plugin registry."""
    reg = Path.home() / ".claude" / "plugins" / "installed_plugins.json"
    if not reg.is_file():
        return {}
    data = json.loads(reg.read_text(encoding="utf-8")).get("plugins", {})
    out = {}
    for key, entries in data.items():
        name = key.split("@", 1)[0]
        if entries:
            out[name] = entries[-1].get("installPath", "")
    return out


def _mcp_registered(name: str) -> bool:
    exe = _claude()
    if not exe:
        return False
    r = subprocess.run([exe, "mcp", "get", name], capture_output=True, text=True)
    return r.returncode == 0


def setup_machine(reviewer_backend: str | None = None, log=print) -> None:
    home = tutu_home()
    (home / "knowledge" / "papers").mkdir(parents=True, exist_ok=True)
    cfg_path = home / "config.toml"
    if not cfg_path.exists():
        shutil.copy2(plugin_root() / "config" / "tutu.default.toml", cfg_path)
        log(f"created {cfg_path}")
    if reviewer_backend:
        text = cfg_path.read_text(encoding="utf-8")
        text = re.sub(r'(?m)^backend\s*=\s*"[^"]*"', f'backend = "{reviewer_backend}"', text, count=1)
        cfg_path.write_text(text, encoding="utf-8")

    aris = installed_plugins().get("aris")
    if not aris:
        log("! aris plugin not installed; skipping ARIS wiring")
        return
    # ARIS helpers (research_wiki.py, verify_papers.py ...) are found through ~/.aris/repo.
    pointer = Path.home() / ".aris" / "repo"
    current = pointer.read_text(encoding="utf-8").strip() if pointer.is_file() else ""
    stale_cache = ".claude" in Path(current).parts and Path(current) != Path(aris)  # plugin was updated
    if not current or not Path(current).is_dir() or stale_cache:
        pointer.parent.mkdir(parents=True, exist_ok=True)
        pointer.write_text(aris + "\n", encoding="utf-8")
        log(f"wrote {pointer} -> {aris}")

    backend = config_mod.get(config_mod.load(), "reviewer.backend", "claude")
    if backend == "claude" and _claude() and not _mcp_registered("claude-review"):
        server = Path(aris) / "mcp-servers" / "claude-review" / "server.py"
        subprocess.run([_claude(), "mcp", "add", "claude-review", "-s", "user", "--",
                        sys.executable, str(server)], check=False)
        log("registered MCP server claude-review (fresh-context Claude reviewer for ARIS skills)")
    if backend == "codex" and not _mcp_registered("codex"):
        log("! reviewer.backend = codex: open Claude Code and run /aris:setup once (needs Codex CLI + login)")


def init_project(root: Path, name: str | None = None, log=print) -> Path:
    pdir = project_dir(root)
    for d in PROJECT_SUBDIRS:
        (pdir / d).mkdir(parents=True, exist_ok=True)
    toml = pdir / "project.toml"
    if not toml.exists():
        tpl = (plugin_root() / "config" / "project.template.toml").read_text(encoding="utf-8")
        toml.write_text(tpl.replace("{name}", name or root.name), encoding="utf-8")
        log(f"created {toml}")
    gi = pdir / ".gitignore"
    if not gi.exists():
        gi.write_text("kb.sqlite\napprovals/*.approved\n", encoding="utf-8")

    sync_aris_reviewer(root, log)

    _ensure_aris_env_section(root, log)

    wiki = root / "research-wiki"
    helper = _aris_wiki_helper()
    if not wiki.exists() and helper:
        subprocess.run([sys.executable, str(helper), "init", str(wiki)], check=False, cwd=root)
    elif not wiki.exists():
        for d in ("papers", "ideas", "experiments", "claims", "graph"):
            (wiki / d).mkdir(parents=True, exist_ok=True)
    return pdir


def sync_aris_reviewer(root: Path, log=print) -> None:
    """Keep <project>/.aris/reviewer.json in line with Tutu's reviewer.backend.

    ARIS only reads the project file; without it every ARIS review step defaults to Codex.
    """
    backend = config_mod.get(config_mod.load(root), "reviewer.backend", "claude")
    want = "claude-code" if backend == "claude" else "codex"
    aris_cfg = root / ".aris" / "reviewer.json"
    current = {}
    if aris_cfg.exists():
        try:
            current = json.loads(aris_cfg.read_text(encoding="utf-8"))
        except ValueError:
            current = {}
    if current.get("backend") == want:
        return
    aris_cfg.parent.mkdir(exist_ok=True)
    aris_cfg.write_text(json.dumps({**current, "backend": want}) + "\n", encoding="utf-8")
    log(f"{aris_cfg}: reviewer backend -> {want}")


ARIS_ENV_SECTION = """
## Local Environment
<!-- read by ARIS run-experiment / experiment-bridge; added by `tutu init` -->
- gpu: local                 # local CUDA/MPS if present, otherwise CPU (pilot-sized configs)
- python: python3            # interpreter of the experiment environment (conda/venv)
"""


def _ensure_aris_env_section(root: Path, log=print) -> None:
    """ARIS experiment skills read `gpu: local|remote|vast|modal` from the project CLAUDE.md."""
    md = root / "CLAUDE.md"
    text = md.read_text(encoding="utf-8") if md.exists() else ""
    if re.search(r"(?m)^##\s+(Local Environment|Remote Server|Vast\.ai|Modal)\b|^-\s*gpu:", text):
        return
    with md.open("a", encoding="utf-8") as f:
        f.write(ARIS_ENV_SECTION)
    log(f"added '## Local Environment' (gpu: local) to {md}")


def _aris_wiki_helper() -> Path | None:
    aris = installed_plugins().get("aris")
    if not aris:
        return None
    for cand in Path(aris).glob("tools/research_wiki.py"):
        return cand
    hits = list(Path(aris).glob("**/research_wiki.py"))
    return hits[0] if hits else None


def doctor(project_root: Path | None = None) -> list[tuple[str, bool, str]]:
    checks: list[tuple[str, bool, str]] = []
    checks.append(("python >= 3.11", sys.version_info >= (3, 11), sys.version.split()[0]))
    checks.append(("claude CLI on PATH", bool(_claude()), _claude() or "install Claude Code"))
    checks.append(("git on PATH", bool(shutil.which("git")), shutil.which("git") or "install git"))
    plugins = installed_plugins()
    for p in REQUIRED_PLUGINS:
        checks.append((f"plugin {p}", p in plugins, plugins.get(p, f"claude plugin install {p}@tutu")))
    try:
        import sqlite3
        sqlite3.connect(":memory:").execute("CREATE VIRTUAL TABLE t USING fts5(a)")
        checks.append(("sqlite FTS5", True, sqlite3.sqlite_version))
    except Exception as e:  # pragma: no cover - platform specific
        checks.append(("sqlite FTS5", False, str(e)))
    pointer = Path.home() / ".aris" / "repo"
    ok = pointer.is_file() and Path(pointer.read_text(encoding="utf-8").strip()).is_dir()
    checks.append(("~/.aris/repo pointer", ok, "run: python -m tutu_runtime setup" if not ok else "ok"))
    backend = config_mod.get(config_mod.load(project_root), "reviewer.backend", "claude")
    mcp = "claude-review" if backend == "claude" else "codex"
    reg = _mcp_registered(mcp)
    fix = "tutu setup" if backend == "claude" else "/aris:setup (needs Codex CLI)"
    checks.append((f"reviewer MCP '{mcp}' (backend={backend})", reg, "ok" if reg else fix))
    dev = device.detect(config_mod.get(config_mod.load(project_root), "compute.device", "auto"))
    checks.append(("compute device", True, f"{dev['device']} ({dev['reason']})"))
    checks.append(("~/.tutu/config.toml", (tutu_home() / "config.toml").is_file(), str(tutu_home())))
    if project_root:
        checks.append(("project .tutu/project.toml", (project_dir(project_root) / "project.toml").is_file(),
                       str(project_root)))
    return checks
