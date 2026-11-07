"""Isolated per-run workspace, created OUTSIDE the repository.

Putting it in the system temp dir matters: Claude Code loads CLAUDE.md files
from the working directory and its parents, so a workspace inside the repo
would leak the project instructions. The agent never learns the repo path.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

STUB = '''"""Write build_weights() here. See the task description you were given."""
import numpy as np


def build_weights():
    raise NotImplementedError
'''


def make_workspace(writable: bool, with_python: bool) -> Path:
    ws = Path(tempfile.mkdtemp(prefix="wi-agent-")).resolve()
    if writable:
        (ws / "build.py").write_text(STUB)
    if with_python:
        make_venv(ws)
    return ws


def make_venv(ws: Path) -> None:
    """A numpy-only interpreter for the 'tools' condition (no sklearn, no project code)."""
    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError("the 'tools' condition needs uv on PATH to build the workspace venv")
    py = f"{sys.version_info.major}.{sys.version_info.minor}"
    subprocess.run([uv, "venv", str(ws / ".venv"), "--python", py, "-q"], check=True)
    subprocess.run([uv, "pip", "install", "-q", "--python", str(ws / ".venv" / "bin" / "python"),
                    f"numpy=={np.__version__}"], check=True)


def snapshot(ws: Path, dest: Path) -> None:
    """Copy the workspace (minus the venv) into the sample folder for provenance."""
    shutil.copytree(ws, dest, ignore=shutil.ignore_patterns(".venv", "__pycache__"), dirs_exist_ok=True)


def cleanup(ws: Path) -> None:
    shutil.rmtree(ws, ignore_errors=True)
