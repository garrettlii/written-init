"""Regression test: run scripts/run_sweep.py as a real subprocess with a
process pool. Catches the missing-__main__-guard bug that broke /smoke on macOS
(experiment.py always uses the "spawn" start method, so this fails on Linux too)."""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CONFIG = """\
tasks: [ring2d]
arms:
  - {name: random, kind: random}
budgets: [0, 16]
seeds: [0, 1]
lr: [1.0e-2]
weight_decay: [0.0]
max_steps: 30
eval_every: 15
patience: 2
workers: 2
"""


def test_parallel_sweep_script(tmp_path):
    cfg = tmp_path / "tiny.yaml"
    cfg.write_text(CONFIG)
    name = f"_pytest_parallel_{os.getpid()}"
    out = ROOT / "results" / name
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src") + os.pathsep + os.environ.get("PYTHONPATH", "")}
    try:
        proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "run_sweep.py"), "--config", str(cfg),
                               "--name", name], capture_output=True, text=True, timeout=300, env=env)
        assert proc.returncode == 0, proc.stderr[-2000:]
        rows = [json.loads(l) for l in (out / "runs.jsonl").read_text().splitlines() if l.strip()]
        assert len(rows) == 4
        # Exactly one provenance line: workers must not re-run the script.
        assert len((out / "provenance.jsonl").read_text().splitlines()) == 1
    finally:
        import shutil
        shutil.rmtree(out, ignore_errors=True)
