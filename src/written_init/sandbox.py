"""Check and run LLM-written `build_weights()` scripts.

Two layers of defense, neither sufficient alone:
  1. Static AST checks block the obvious ways to fit weights instead of
     writing them: randomness, linear solvers, file/network access, dynamic
     code, and attribute tricks that could smuggle those in.
  2. Execution in a separate interpreter with a timeout.
A determined script could still hand-roll a fitting loop (e.g. enumerate inputs
and run gradient descent in pure numpy). Static checks cannot rule that out, so
every build.py is saved and must be audited (see the /audit-init skill) before
its results are reported.
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ALLOWED_IMPORTS = {"numpy", "math", "itertools", "functools"}
BANNED_NAMES = {
    "exec", "eval", "compile", "open", "input", "__import__", "getattr", "setattr", "delattr",
    "globals", "locals", "vars", "breakpoint", "memoryview",
}
# Attribute names that indicate sampling, fitting or solving rather than writing.
BANNED_ATTRS = {
    "random", "lstsq", "pinv", "solve", "inv", "tensorsolve", "tensorinv", "svd", "eig", "eigh",
    "qr", "cholesky", "polyfit", "load", "loadtxt", "genfromtxt", "fromfile", "save", "savez",
    "tofile", "frombuffer",
}

CODE_BLOCK = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.DOTALL)


def extract_code(text: str) -> str | None:
    """Pick the python block that defines build_weights (last one wins)."""
    blocks = [b for b in CODE_BLOCK.findall(text) if "def build_weights" in b]
    return blocks[-1].strip() + "\n" if blocks else None


def check_source(src: str) -> list[str]:
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return [f"syntax error: {e}"]
    problems: list[str] = []
    defines_build = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[0] not in ALLOWED_IMPORTS:
                    problems.append(f"line {node.lineno}: import of {a.name!r} not allowed")
                if a.name.startswith("numpy.random"):
                    problems.append(f"line {node.lineno}: numpy.random not allowed")
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod.split(".")[0] not in ALLOWED_IMPORTS or "random" in mod.split("."):
                problems.append(f"line {node.lineno}: import from {mod!r} not allowed")
            for a in node.names:
                if a.name in BANNED_ATTRS or a.name in BANNED_NAMES:
                    problems.append(f"line {node.lineno}: importing {a.name!r} not allowed")
        elif isinstance(node, ast.Name) and node.id in BANNED_NAMES:
            problems.append(f"line {node.lineno}: use of {node.id!r} not allowed")
        elif isinstance(node, ast.Attribute):
            if node.attr in BANNED_ATTRS:
                problems.append(f"line {node.lineno}: use of .{node.attr} not allowed")
            if node.attr.startswith("__"):
                problems.append(f"line {node.lineno}: dunder attribute {node.attr!r} not allowed")
        elif isinstance(node, ast.FunctionDef) and node.name == "build_weights":
            defines_build = True
    if not defines_build:
        problems.append("no top-level function build_weights() defined")
    return problems


_RUNNER = r"""
import importlib.util, json, sys
import numpy as np
spec = importlib.util.spec_from_file_location("build", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
w = mod.build_weights()
if not isinstance(w, dict):
    raise TypeError(f"build_weights() returned {type(w).__name__}, expected dict")
arrs = {str(k): np.asarray(v, dtype=np.float64) for k, v in w.items()}
np.savez(sys.argv[2], **arrs)
print(json.dumps({k: list(v.shape) for k, v in arrs.items()}))
"""


def run_build(build_py: Path, out_npz: Path, timeout_s: int = 120) -> tuple[bool, str]:
    """Execute build_weights() in a fresh interpreter. Returns (ok, message)."""
    with tempfile.TemporaryDirectory() as td:
        runner = Path(td) / "runner.py"
        runner.write_text(_RUNNER)
        try:
            proc = subprocess.run(
                [sys.executable, "-I", "-B", str(runner), str(build_py), str(out_npz)],
                capture_output=True, text=True, timeout=timeout_s, cwd=td,
            )
        except subprocess.TimeoutExpired:
            return False, f"build_weights() exceeded the {timeout_s}s time limit"
    if proc.returncode != 0:
        tail = "\n".join(proc.stderr.strip().splitlines()[-15:])
        return False, f"build_weights() raised an error:\n{tail}"
    try:
        json.loads(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return False, "build_weights() produced no output"
    return True, "ok"
