"""The hand-built reference inits should solve their tasks zero-shot. If this
fails, either a task definition or the forward pass changed."""

import numpy as np
import pytest

from written_init.init_arms import load_weights
from written_init.models import evaluate
from written_init.paths import INITS
from written_init.sandbox import run_build
from written_init.tasks import get_task

MIN_ACC = {"sparse_parity": 1.0, "gridnav": 1.0, "ring2d": 0.98}


@pytest.mark.parametrize("task_name", sorted(MIN_ACC))
def test_reference_zero_shot(task_name, tmp_path):
    task = get_task(task_name)
    ok, msg = run_build(INITS / task_name / "reference" / "sample_00" / "build.py", tmp_path / "w.npz")
    assert ok, msg
    params = load_weights(task, tmp_path / "w.npz")
    n = task.split_size("test") if hasattr(task, "split_size") else 2000
    X, y = task.sample(n, np.random.default_rng(0), "test")
    acc, _ = evaluate(params, X, y, task.activation)
    assert acc >= MIN_ACC[task_name]
