"""`tutu doctor --skills`: verify that the four orchestrated skill repos are installed completely
and that what each mapped skill needs at runtime is present.

Checks (each row: OK / MISSING / OPTIONAL / INFO):
  plugins   expected skill counts per plugin; every SKILL.md frontmatter parses (name + description)
  links     relative files referenced by mapped skills (references/, scripts/, shared-references/) exist
  helpers   ARIS helper scripts named by mapped skills resolve via the ARIS resolver chain (~/.aris/repo)
  python    libraries from requirements-skills.txt import in the Tutu venv (tutu-py)
  tools     latexmk / pdflatex / xelatex / drawio; screen + ssh (Linux-only skills)
  keys      optional API keys
  review    live round-trip through the claude-review MCP server (with --live)
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

from . import sysdeps
from .paths import plugin_root
from .setup import installed_plugins

# Skill counts of the pinned upstream layouts (top-level skills only; ARIS codex mirrors excluded).
EXPECTED = {"superpowers": 15, "aris": 87, "supervisor-skills": 12, "humanizer": 1}
PY_MODULES = {"requests": "requests", "yaml": "pyyaml", "numpy": "numpy", "scipy": "scipy", "pandas": "pandas",
              "matplotlib": "matplotlib", "seaborn": "seaborn", "PIL": "Pillow", "pptx": "python-pptx",
              "pypdf": "pypdf"}
OPTIONAL_MODULES = {"deepxiv_sdk": "deepxiv-sdk (aris:deepxiv)", "exa_py": "exa-py (aris:exa-search)",
                    "wandb": "wandb (aris:training-check)"}
OPTIONAL_KEYS = {"SEMANTIC_SCHOLAR_API_KEY": "higher Semantic Scholar rate limits",
                 "EXA_API_KEY": "aris:exa-search", "WANDB_API_KEY": "aris:training-check / wandb logging",
                 "GEMINI_API_KEY": "aris:paper-illustration (AI figures)"}

Row = tuple[str, str, str, str]  # (group, item, status, detail)


def _skill_files(root: Path) -> list[Path]:
    files = list(root.glob("skills/*/SKILL.md"))
    if not files and (root / "SKILL.md").is_file():  # humanizer: single skill at repo root
        files = [root / "SKILL.md"]
    return files


def _frontmatter(text: str) -> dict:
    m = re.match(r"---\r?\n(.*?)\r?\n---", text, re.S)
    if not m:
        return {}
    keys = {}
    for k in ("name", "description"):
        km = re.search(rf"^{k}:\s*(.*)$", m.group(1), re.M)
        if km:
            keys[k] = km.group(1).strip()
    return keys


def aris_repo() -> Path | None:
    env = os.environ.get("ARIS_REPO")
    if env and Path(env).is_dir():
        return Path(env)
    ptr = Path.home() / ".aris" / "repo"
    if ptr.is_file():
        p = Path(ptr.read_text(encoding="utf-8").strip())
        if p.is_dir():
            return p
    return None


def check_plugins(plugins: dict[str, str]) -> list[Row]:
    rows: list[Row] = []
    for name, expected in EXPECTED.items():
        root = Path(plugins.get(name, ""))
        if not plugins.get(name) or not root.is_dir():
            rows.append(("plugins", name, "MISSING", f"claude plugin install {name}@tutu"))
            continue
        files = _skill_files(root)
        bad = [f.parent.name for f in files if not {"name", "description"} <= _frontmatter(
            f.read_text(encoding="utf-8", errors="replace")).keys()]
        status = "OK" if len(files) >= expected and not bad else "MISSING"
        detail = f"{len(files)} skills (expected ≥ {expected})" + (f"; bad frontmatter: {bad}" if bad else "")
        rows.append(("plugins", name, status, detail))
    return rows


def _mapped_skills() -> dict[str, list[str]]:
    m = tomllib.loads((plugin_root() / "config" / "skill-map.toml").read_text(encoding="utf-8"))
    out: dict[str, list[str]] = {}
    for agent in m.values():
        for s in agent["preload"] + agent["borrow"]:
            plugin, skill = s.split(":", 1)
            out.setdefault(plugin, [])
            if skill not in out[plugin]:
                out[plugin].append(skill)
    return out


def _skill_dir(plugin_root_: Path, skill: str) -> Path:
    d = plugin_root_ / "skills" / skill
    return d if d.is_dir() else plugin_root_


LINK = re.compile(r"\]\((?!https?:|#|mailto:)([^)\s]+?)(?:#[^)]*)?\)")
SCRIPT_REF = re.compile(r"(?<![\w/$.-])((?:scripts|references)/[\w./-]+\.(?:py|sh|md|json|txt|tex|ya?ml))")
HELPER_REF = re.compile(r"tools/([\w-]+\.(?:py|sh))")
# Paths that upstream SKILL.md files mention only as illustrations inside worked examples.
KNOWN_EXAMPLES = {"research-implement-feature: scripts/bench_eviction.py"}


def check_links_and_helpers(plugins: dict[str, str]) -> list[Row]:
    rows: list[Row] = []
    repo = aris_repo()
    for plugin, skills in _mapped_skills().items():
        root = Path(plugins.get(plugin, ""))
        if not root.is_dir():
            continue
        missing_links, missing_helpers, helpers = [], set(), set()
        for skill in skills:
            sdir = _skill_dir(root, skill)
            text = (sdir / "SKILL.md").read_text(encoding="utf-8", errors="replace")
            body = re.sub(r"```.*?```", "", text, flags=re.S)  # links in code blocks are examples
            prose = re.sub(r"``.*?``|`[^`\n]*`", "", body)       # so is markdown syntax shown inline
            for ref in set(LINK.findall(prose)) | set(SCRIPT_REF.findall(body)):
                ref = ref.strip("<>")
                if "<" in ref or "*" in ref or ref.startswith("/"):
                    continue
                if not (sdir / ref).resolve().exists() and not (root / ref).exists() \
                        and f"{skill}: {ref}" not in KNOWN_EXAMPLES:
                    missing_links.append(f"{skill}: {ref}")
            if plugin == "aris":
                helpers |= {(h, sdir) for h in HELPER_REF.findall(text)}
        for h, sdir in sorted(helpers):
            # resolver chain: <repo>/tools/<h>, or a single-skill helper in the skill's own scripts/
            if not ((repo and (repo / "tools" / h).exists()) or (sdir / "scripts" / h).exists()):
                missing_helpers.add(h)
        rows.append(("links", plugin, "OK" if not missing_links else "MISSING",
                     f"{len(skills)} mapped skills" + (f"; missing: {missing_links[:8]}" if missing_links else "")))
        if plugin == "aris":
            rows.append(("helpers", "ARIS tools/ via ~/.aris/repo",
                         "OK" if repo and not missing_helpers else "MISSING",
                         f"{len(helpers) - len(missing_helpers)}/{len(helpers)} helper references resolve"
                         + (f"; missing: {sorted(missing_helpers)}" if missing_helpers else f" (repo: {repo})")))
    return rows


def check_python() -> list[Row]:
    py = sysdeps.venv_python()
    if not py.exists():
        return [("python", "Tutu venv", "MISSING", "python install.py (creates ~/.tutu/venv)")]
    rows: list[Row] = [("python", "Tutu venv", "OK", str(py))]
    probe = "import importlib.util,json,sys;print(json.dumps({m: importlib.util.find_spec(m) is not None for m in sys.argv[1:]}))"
    mods = list(PY_MODULES) + list(OPTIONAL_MODULES)
    found = json.loads(subprocess.run([str(py), "-c", probe, *mods], capture_output=True, text=True).stdout or "{}")
    missing = [PY_MODULES[m] for m in PY_MODULES if not found.get(m)]
    rows.append(("python", "required libraries", "OK" if not missing else "MISSING",
                 "all present" if not missing else f"tutu-py -m pip install {' '.join(missing)}"))
    for m, what in OPTIONAL_MODULES.items():
        rows.append(("python", what, "OK" if found.get(m) else "OPTIONAL",
                     "installed" if found.get(m) else f"tutu-py -m pip install {what.split()[0]}"))
    return rows


def check_tools() -> list[Row]:
    rows: list[Row] = []
    for t in ("latexmk", "pdflatex", "xelatex", "bibtex"):
        rows.append(("tools", t, "OK" if shutil.which(t) else "MISSING",
                     shutil.which(t) or "python install.py --with-latex"))
    d = sysdeps.drawio_path()
    rows.append(("tools", "drawio", "OK" if d else "OPTIONAL", d or "python install.py --with-drawio"))
    if d and os.name != "nt" and sys.platform != "darwin" and not os.environ.get("DISPLAY"):
        rows.append(("tools", "xvfb-run (headless drawio export)", "OK" if shutil.which("xvfb-run") else "MISSING",
                     shutil.which("xvfb-run") or "apt-get install xvfb"))
    for t, why in (("screen", "aris:experiment-queue / remote runs"), ("ssh", "remote GPU servers")):
        rows.append(("tools", t, "OK" if shutil.which(t) else "OPTIONAL",
                     shutil.which(t) or f"only needed for {why} (Linux)"))
    return rows


def check_keys() -> list[Row]:
    return [("keys", k, "OK" if os.environ.get(k) else "OPTIONAL", f"for {why}") for k, why in OPTIONAL_KEYS.items()]


def live_review(timeout: int = 240) -> Row:
    """Round-trip one tiny prompt through the claude-review MCP server (spawns a separate `claude -p`)."""
    repo = aris_repo()
    server = repo / "mcp-servers" / "claude-review" / "server.py" if repo else None
    if not server or not server.is_file():
        return ("review", "claude-review live", "MISSING", "ARIS repo not resolved")
    msgs = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "tutu", "version": "0"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
         "params": {"name": "review", "arguments": {"prompt": "Reply with exactly: TUTU_REVIEW_OK", "tools": ""}}},
    ]
    try:
        r = subprocess.run([sys.executable, str(server)], input="".join(json.dumps(m) + "\n" for m in msgs),
                           capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return ("review", "claude-review live", "MISSING", f"timed out after {timeout}s")
    for line in r.stdout.splitlines():
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if msg.get("id") == 2:
            if "error" in msg or msg.get("result", {}).get("isError"):
                return ("review", "claude-review live", "MISSING", json.dumps(msg)[:300])
            payload = json.loads(msg["result"]["content"][0]["text"])
            ok = bool(payload.get("threadId")) and "TUTU_REVIEW_OK" in payload.get("response", "")
            return ("review", "claude-review live", "OK" if ok else "MISSING",
                    f"threadId={payload.get('threadId')} response={payload.get('response', '')[:60]!r}")
    return ("review", "claude-review live", "MISSING", (r.stderr or r.stdout)[-300:])


def run(live: bool = False) -> list[Row]:
    plugins = installed_plugins()
    rows = check_plugins(plugins) + check_links_and_helpers(plugins) + check_python() + check_tools() + check_keys()
    if live:
        rows.append(live_review())
    return rows
