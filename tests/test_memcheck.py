"""scripts/memcheck_digits.py, the auditor-side memorization check for digits8x8 samples."""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from sklearn.datasets import load_digits

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("memcheck_digits", ROOT / "scripts" / "memcheck_digits.py")
mc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mc)
X = load_digits().data / 16.0


def test_a_one_pixel_shifted_copy_is_found_only_with_shifts():
    cand = mc.shift(X[3], 1, -1)[None]
    (d0, _, _), = mc.nearest(cand, X, shifts=[(0, 0)])
    (d, i, s), = mc.nearest(cand, X)
    assert (i, s) == (3, (1, -1)) and d < 1e-6 and d0 > 0.33


BUILD = """import numpy as np
COL = {col}
def build_weights():
    W0 = np.zeros((64, 64)); W0[:, 7] = np.array(COL)
    return {{"W0": W0, "b0": np.zeros(64), "W1": np.zeros((64, 32)), "b1": np.zeros(32),
            "W2": np.zeros((32, 10)), "b2": np.zeros(10)}}
"""
r, c = np.mgrid[0:8, 0:8]
BLOB = np.exp(-((r - 3.5) ** 2 + (c - 3.5) ** 2) / 4).ravel()     # digit-sized, but no real image


@pytest.mark.parametrize("col,code,needle", [
    (0.5 - 3 * mc.shift(X[5], 0, 1), 1, "W0[:, 7] negated ~ load_digits index 5"),   # scaled, negated, shifted copy
    (BLOB, 0, "no candidate below the floor"),
])
def test_memcheck_rejects_a_real_image_hidden_in_a_w0_column(tmp_path, col, code, needle):
    (tmp_path / "build.py").write_text(BUILD.format(col=[float(v) for v in col]))
    ns = {}
    exec((tmp_path / "build.py").read_text(), ns)
    np.savez(tmp_path / "weights.npz", **ns["build_weights"]())
    proc = subprocess.run([sys.executable, "-B", str(ROOT / "scripts" / "memcheck_digits.py"), str(tmp_path)],
                          capture_output=True, text=True, timeout=300,
                          env={**os.environ, "PYTHONPATH": str(ROOT / "src")})
    assert proc.returncode == code, proc.stdout + proc.stderr
    assert needle in proc.stdout and "checking W0 columns only" in proc.stdout
