"""Run every inits/<task or family>/reference/sample_*/build.py through the sandbox.

Reference inits exist only to test the pipeline end to end without API calls.
They are never an experimental arm in a reported result.
"""

import sys

from written_init.init_arms import load_weights
from written_init.models import evaluate
from written_init.paths import INITS
from written_init.sandbox import check_source, run_build
from written_init.tasks import FAMILIES, family_instances, get_task

failed = False
for build in sorted(INITS.glob("*/reference/sample_*/build.py")):
    name = build.parents[2].name
    tasks = [get_task(t) for t in family_instances(name)] if name in FAMILIES else [get_task(name)]
    problems = check_source(build.read_text())
    if problems:
        print(f"[FAIL] {build}: {problems}"); failed = True; continue
    ok, msg = run_build(build, build.parent / "weights.npz")
    if not ok:
        print(f"[FAIL] {build}: {msg}"); failed = True; continue
    for task in tasks:  # a family's reference is checked on every instance
        params = load_weights(task, build.parent / "weights.npz")
        X, y = task.sample(task.split_size("test") if hasattr(task, "split_size") else 2000,
                           __import__("numpy").random.default_rng(0), "test")
        acc, _ = evaluate(params, X, y, task.activation)
        print(f"[ok] {task.name:18s} reference zero-shot test acc = {acc:.4f}")
sys.exit(1 if failed else 0)
