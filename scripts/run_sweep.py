"""Run a sweep defined by a YAML config. Resumable: rerunning skips finished jobs.

  uv run python scripts/run_sweep.py --config configs/smoke.yaml
  uv run python scripts/run_sweep.py --config configs/default.yaml --name main_v1 --workers 8
"""

import os

# One BLAS thread per worker; must be set before numpy is imported anywhere.
# Spawned workers inherit the environment, so this covers them too.
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")  # macOS Accelerate

import argparse  # noqa: E402
import json  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
from datetime import datetime, timezone  # noqa: E402
from pathlib import Path  # noqa: E402

from written_init.experiment import SweepConfig, run_sweep  # noqa: E402
from written_init.paths import RESULTS, ROOT  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--config", required=True)
    p.add_argument("--name", default=None, help="results/<name>/ (default: config file stem)")
    p.add_argument("--workers", type=int, default=None)
    a = p.parse_args()

    cfg = SweepConfig.load(a.config)
    if a.workers is not None:
        cfg.workers = a.workers
    out = RESULTS / (a.name or Path(a.config).stem)
    out.mkdir(parents=True, exist_ok=True)

    # Provenance: config used and code version.
    shutil.copy(a.config, out / "config.yaml")
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True,
                                    text=True).stdout.strip())
    except FileNotFoundError:
        commit, dirty = "", None
    with open(out / "provenance.jsonl", "a") as fh:
        fh.write(json.dumps({"started": datetime.now(timezone.utc).isoformat(), "git_commit": commit,
                             "git_dirty": dirty, "config": a.config}) + "\n")

    run_sweep(cfg, out)
    print(f"done -> {out}. Next: uv run python scripts/analyze.py {out}")


# Required: worker processes re-import this file under the "spawn" start method
# (the default on macOS and Windows). Without this guard every worker would
# rerun the whole sweep and crash the pool.
if __name__ == "__main__":
    main()
