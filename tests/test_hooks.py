import json
import os
import shutil
import subprocess
import sys

import pytest

from conftest import REPO

BASH = shutil.which("bash")


def run_hook(script, event, env_home):
    env = dict(os.environ, HOME=str(env_home), USERPROFILE=str(env_home), TUTU_HOME=str(env_home / ".tutu"),
               TUTU_PYTHON=sys.executable)
    r = subprocess.run([BASH, str(REPO / "hooks" / "run.sh"), script], input=json.dumps(event),
                       capture_output=True, text=True, env=env, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout) if r.stdout.strip() else None


@pytest.mark.skipif(BASH is None, reason="bash not available")
def test_guard_hook_denies(project, home):
    out = run_hook("guard_hook.py", {"tool_name": "Bash", "tool_input": {"command": "rm -rf data/raw"},
                                     "cwd": str(project)}, home)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


@pytest.mark.skipif(BASH is None, reason="bash not available")
def test_guard_hook_silent_on_allow(project, home):
    assert run_hook("guard_hook.py", {"tool_name": "Bash", "tool_input": {"command": "ls"},
                                      "cwd": str(project)}, home) is None


@pytest.mark.skipif(BASH is None, reason="bash not available")
def test_session_context(project, home):
    out = run_hook("session_context.py", {"cwd": str(project)}, home)
    assert "Project 'demo'" in out["hookSpecificOutput"]["additionalContext"]
    assert run_hook("session_context.py", {"cwd": str(home)}, home) is None


@pytest.mark.skipif(BASH is None, reason="bash not available")
def test_provenance_nudge(project, home):
    out = run_hook("provenance_log.py", {"tool_name": "Bash", "tool_input": {"command": "python train.py --seed 1"},
                                         "cwd": str(project)}, home)
    assert "provenance" in out["hookSpecificOutput"]["additionalContext"]
    assert (project / ".tutu" / "trace.jsonl").read_text().count("experiment_command") == 1
