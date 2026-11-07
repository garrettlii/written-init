import numpy as np

from written_init.init_arms import init_random
from written_init.models import evaluate
from written_init.optim import newton_schulz5
from written_init.tasks import get_task
from written_init.train import TrainConfig, train


def test_newton_schulz_pushes_singular_values_near_one():
    G = np.random.default_rng(0).normal(size=(32, 48))
    s = np.linalg.svd(newton_schulz5(G), compute_uv=False)
    assert s.min() > 0.5 and s.max() < 1.5


def _fit(opt, **kw):
    task = get_task("ring2d")
    rng = np.random.default_rng(0)
    X, y = task.sample(512, rng, "train")
    Xv, yv = task.sample(256, np.random.default_rng(1), "val")
    p0 = init_random(task, np.random.default_rng(2))
    acc0, _ = evaluate(p0, Xv, yv, task.activation)
    p, info = train(p0, task.activation, X, y, Xv, yv,
                    TrainConfig(optimizer=opt, max_steps=800, patience=100, **kw), np.random.default_rng(3))
    return acc0, info["val_acc"]


def test_adamw_learns():
    acc0, acc = _fit("adamw", lr=1e-2)
    assert acc > max(acc0, 0.85)


def test_muon_learns():
    acc0, acc = _fit("muon", lr=1e-2, muon_lr=0.02)
    assert acc > max(acc0, 0.85)
