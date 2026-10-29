"""Dependencies the orchestrated skills need beyond Claude Code itself.

* Tutu venv (~/.tutu/venv): Python libraries used by ARIS helpers and by analysis/figure
  skills. Kept separate from research environments; exposed as the `tutu-py` command.
* System tools (opt-in): LaTeX (paper-compile, paper-writing, paper-slides, citation-audit)
  and draw.io desktop (supervisor-skills:drawio-reconstruction).
"""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

from .paths import plugin_root, tutu_home

LINUX_TOOLS_APT = ["screen", "openssh-client", "rsync"]  # aris:experiment-queue / remote runs
LATEX_APT = ["latexmk", "texlive-latex-extra", "texlive-fonts-recommended", "texlive-science",
             "texlive-bibtex-extra", "biber", "texlive-xetex"]
DRAWIO_RELEASES = "https://api.github.com/repos/jgraph/drawio-desktop/releases/latest"


def venv_dir() -> Path:
    return tutu_home() / "venv"


def venv_python() -> Path:
    v = venv_dir()
    return v / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def requirements_file() -> Path:
    return plugin_root() / "requirements-skills.txt"


def create_venv(extras: list[str] = (), log=print) -> Path:
    py = venv_python()
    if not py.exists():
        log(f"creating Tutu venv at {venv_dir()}")
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir())], check=True)
    subprocess.run([str(py), "-m", "pip", "install", "-q", "--upgrade", "pip"], check=False)
    subprocess.run([str(py), "-m", "pip", "install", "-q", "-r", str(requirements_file())], check=True)
    if extras:
        subprocess.run([str(py), "-m", "pip", "install", "-q", *extras], check=True)
    log(f"Tutu venv ready: {py}")
    return py


def _run_root(cmd: list[str]) -> int:
    if os.name != "nt" and hasattr(os, "geteuid") and os.geteuid() != 0 and shutil.which("sudo"):
        cmd = ["sudo", *cmd]
    print("$", " ".join(cmd), flush=True)
    return subprocess.run(cmd, env=dict(os.environ, DEBIAN_FRONTEND="noninteractive")).returncode


def install_latex(log=print) -> bool:
    if shutil.which("latexmk") and shutil.which("pdflatex"):
        log("LaTeX already installed")
        return True
    system = platform.system()
    if system == "Linux" and shutil.which("apt-get"):
        _run_root(["apt-get", "update", "-q"])
        return _run_root(["apt-get", "install", "-y", "-q", "--no-install-recommends",
                          *LATEX_APT, *LINUX_TOOLS_APT]) == 0
    if system == "Windows" and shutil.which("winget"):
        ok = subprocess.run(["winget", "install", "-e", "--id", "MiKTeX.MiKTeX", "--accept-package-agreements",
                             "--accept-source-agreements"]).returncode == 0
        log("MiKTeX installed; latexmk needs Perl (e.g. `winget install StrawberryPerl.StrawberryPerl`). "
            "Restart the terminal so PATH updates.")
        return ok
    if system == "Darwin" and shutil.which("brew"):
        return subprocess.run(["brew", "install", "--cask", "mactex-no-gui"]).returncode == 0
    log("Install a TeX distribution manually: TeX Live (Linux), MiKTeX (Windows) or MacTeX (macOS).")
    return False


def drawio_path() -> str | None:
    for cand in (os.environ.get("DRAWIO_PATH"), shutil.which("drawio"), shutil.which("draw.io"),
                 "/opt/drawio/drawio", "/Applications/draw.io.app/Contents/MacOS/draw.io",
                 os.path.expandvars(r"%ProgramFiles%\draw.io\draw.io.exe"),
                 os.path.expandvars(r"%LOCALAPPDATA%\Programs\draw.io\draw.io.exe")):
        if cand and Path(cand).exists():
            return cand
    return None


HEADLESS_WRAPPER = """#!/usr/bin/env bash
# draw.io for headless Linux (written by Tutu): virtual display when there is no $DISPLAY,
# and --no-sandbox when running as root (Electron refuses otherwise).
real="{real}"
extra=()
[ "$(id -u)" = "0" ] && extra+=(--no-sandbox)
if [ -z "${{DISPLAY:-}}" ] && command -v xvfb-run >/dev/null 2>&1; then
  exec xvfb-run -a "$real" "$@" "${{extra[@]}}"
fi
exec "$real" "$@" "${{extra[@]}}"
"""


def configure_drawio_headless(log=print) -> str | None:
    """On Linux, point DRAWIO_PATH (read first by drawio-reconstruction's export_drawio.py)
    at a wrapper that works on servers and as root. Set through Claude Code settings `env`."""
    real = drawio_path()
    if not real or platform.system() != "Linux" or "drawio-headless" in real:
        return real
    wrapper = tutu_home() / "bin" / "drawio-headless"
    wrapper.parent.mkdir(parents=True, exist_ok=True)
    wrapper.write_text(HEADLESS_WRAPPER.format(real=real), encoding="utf-8")
    wrapper.chmod(0o755)
    settings = Path.home() / ".claude" / "settings.json"
    data = json.loads(settings.read_text(encoding="utf-8")) if settings.is_file() else {}
    if data.get("env", {}).get("DRAWIO_PATH") != str(wrapper):
        data.setdefault("env", {})["DRAWIO_PATH"] = str(wrapper)
        settings.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        log(f"set env DRAWIO_PATH={wrapper} in {settings}")
    return str(wrapper)


def install_drawio(log=print) -> bool:
    if drawio_path():
        log(f"draw.io already installed: {configure_drawio_headless(log)}")
        return True
    system = platform.system()
    if system == "Linux" and shutil.which("apt-get"):
        arch = {"x86_64": "amd64", "aarch64": "arm64"}.get(platform.machine(), "amd64")
        rel = json.load(urllib.request.urlopen(DRAWIO_RELEASES, timeout=60))
        asset = next(a for a in rel["assets"] if re.fullmatch(rf"drawio-{arch}-[\d.]+\.deb", a["name"]))
        deb = Path("/tmp") / asset["name"]
        log(f"downloading {asset['name']}")
        urllib.request.urlretrieve(asset["browser_download_url"], deb)
        ok = _run_root(["apt-get", "install", "-y", "-q", str(deb), "xvfb", "xauth"]) == 0
        deb.unlink(missing_ok=True)
        configure_drawio_headless(log)
        return ok
    if system == "Windows" and shutil.which("winget"):
        return subprocess.run(["winget", "install", "-e", "--id", "JGraph.Draw", "--accept-package-agreements",
                               "--accept-source-agreements"]).returncode == 0
    if system == "Darwin" and shutil.which("brew"):
        return subprocess.run(["brew", "install", "--cask", "drawio"]).returncode == 0
    log("Install draw.io desktop from https://github.com/jgraph/drawio-desktop/releases")
    return False
