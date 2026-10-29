"""Agents' `skills:` frontmatter must equal config/skill-map.toml, and every mapped skill must exist."""

import json
import re
import tomllib
from pathlib import Path

import pytest

from conftest import REPO

SKILL_MAP = tomllib.loads((REPO / "config" / "skill-map.toml").read_text())
AGENTS = sorted((REPO / "agents").glob("*.md"))


def frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    fm = re.match(r"---\n(.*?)\n---\n", text, re.S).group(1)
    out, key = {}, None
    for line in fm.splitlines():
        if m := re.match(r"^(\w[\w-]*):\s*(.*)$", line):
            key, val = m.groups()
            out[key] = val if val else []
        elif m := re.match(r"^\s+-\s+(.+)$", line):
            out[key].append(m.group(1).strip())
    return out


def test_seven_agents():
    assert {p.stem for p in AGENTS} == set(SKILL_MAP) and len(AGENTS) == 7


@pytest.mark.parametrize("path", AGENTS, ids=lambda p: p.stem)
def test_agent_matches_map(path):
    fm = frontmatter(path)
    assert fm["name"] == path.stem
    assert fm["skills"] == SKILL_MAP[path.stem]["preload"]
    assert 5 <= len(fm["skills"]) <= 8
    assert "Skill" in fm["tools"], "agents must be able to borrow skills"
    assert "${CLAUDE_PLUGIN_ROOT}/config/protocol.md" in path.read_text()


def test_reviewer_is_read_only():
    assert "Edit" not in [t.strip() for t in frontmatter(REPO / "agents" / "reviewer.md")["tools"].split(",")]


def _installed_skills() -> set[str] | None:
    reg = Path.home() / ".claude" / "plugins" / "installed_plugins.json"
    if not reg.is_file():
        return None
    names = set()
    for key, entries in json.loads(reg.read_text()).get("plugins", {}).items():
        plugin = key.split("@")[0]
        root = Path(entries[-1]["installPath"])
        for sk in list(root.glob("skills/*/SKILL.md")) + list(root.glob("SKILL.md")):
            m = re.search(r"^name:\s*(\S+)", sk.read_text(encoding="utf-8", errors="replace"), re.M)
            names.add(f"{plugin}:{m.group(1) if m else sk.parent.name}")
    return names


def test_mapped_skills_exist_when_installed():
    installed = _installed_skills()
    if not installed:
        pytest.skip("skill plugins not installed on this machine")
    wanted = {s for a in SKILL_MAP.values() for s in a["preload"] + a["borrow"]}
    assert sorted(wanted - installed) == []
