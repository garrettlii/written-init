from written_init.experiment import Arm, SweepConfig, _train_pool, run_job
from written_init.tasks import get_task


def _cfg(**kw):
    base = dict(tasks=["sparse_parity"], arms=[], budgets=[0, 16, 64], seeds=[0], lr=[1e-3],
                weight_decay=[0.0], max_steps=20, eval_every=10, patience=2, workers=1)
    base.update(kw)
    return SweepConfig(**base)


def test_training_sets_are_paired_and_nested():
    task = get_task("sparse_parity")
    X1, y1 = _train_pool(task, seed=3, max_budget=64)
    X2, y2 = _train_pool(task, seed=3, max_budget=64)
    assert (X1 == X2).all() and (y1 == y2).all()       # same seed -> same data for every arm
    X3, _ = _train_pool(task, seed=4, max_budget=64)
    assert not (X1 == X3).all()                         # different seed -> different data


def test_run_job_rows():
    cfg = _cfg()
    row0 = run_job(cfg, "sparse_parity", Arm("random", "random"), 0, 0)
    assert row0["test_acc"] == row0["init_test_acc"] and row0["hp"] is None
    row = run_job(cfg, "sparse_parity", Arm("random", "random"), 16, 0)
    assert 0.0 <= row["test_acc"] <= 1.0 and len(row["hp_results"]) == 1


def test_missing_source_is_skipped():
    cfg = _cfg()
    assert run_job(cfg, "digits8x8", Arm("x", "written", source="no-such-model"), 16, 0) is None
