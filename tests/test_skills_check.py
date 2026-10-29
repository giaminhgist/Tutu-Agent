from pathlib import Path

from tutu_runtime import provenance, setup, skills_check, sysdeps


def _fake_plugin(root: Path, skills: dict[str, str]) -> None:
    for name, body in skills.items():
        d = root / "skills" / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(f"---\nname: {name}\ndescription: test\n---\n{body}\n")


def test_check_plugins_counts_and_frontmatter(tmp_path, monkeypatch):
    monkeypatch.setattr(skills_check, "EXPECTED", {"demo": 2})
    _fake_plugin(tmp_path / "demo", {"a": "x", "b": "y"})
    (tmp_path / "demo" / "skills" / "c").mkdir()
    (tmp_path / "demo" / "skills" / "c" / "SKILL.md").write_text("no frontmatter")
    rows = skills_check.check_plugins({"demo": str(tmp_path / "demo")})
    assert rows[0][2] == "MISSING" and "bad frontmatter: ['c']" in rows[0][3]


def test_missing_plugin(tmp_path, monkeypatch):
    monkeypatch.setattr(skills_check, "EXPECTED", {"demo": 1})
    assert skills_check.check_plugins({})[0][2] == "MISSING"


def test_aris_env_section_added_once(project):
    setup._ensure_aris_env_section(project, log=lambda *_: None)
    setup._ensure_aris_env_section(project, log=lambda *_: None)
    text = (project / "CLAUDE.md").read_text()
    assert text.count("## Local Environment") == 1 and "- gpu: local" in text


def test_aris_env_section_respects_existing(project):
    (project / "CLAUDE.md").write_text("# p\n## Remote Server\n- gpu: remote\n")
    setup._ensure_aris_env_section(project, log=lambda *_: None)
    assert "Local Environment" not in (project / "CLAUDE.md").read_text()


def test_provenance_never_freezes_tutu_venv(home, monkeypatch):
    venv_py = sysdeps.venv_python()
    venv_py.parent.mkdir(parents=True)
    venv_py.write_text("")
    monkeypatch.setattr(provenance.shutil, "which", lambda n: str(venv_py) if n == "python3" else "/usr/bin/python")
    assert provenance.target_python() == "/usr/bin/python"
    assert provenance.target_python("/opt/env/bin/python") == "/opt/env/bin/python"


def test_sync_aris_reviewer(project):
    import json
    setup.sync_aris_reviewer(project, log=lambda *_: None)
    assert json.loads((project / ".aris/reviewer.json").read_text())["backend"] == "claude-code"
    (project / ".aris/reviewer.json").write_text('{"backend": "codex", "model": "x"}')
    setup.sync_aris_reviewer(project, log=lambda *_: None)
    assert json.loads((project / ".aris/reviewer.json").read_text()) == {"backend": "claude-code", "model": "x"}
