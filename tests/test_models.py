import numpy as np
import pytest

from written_init.models import evaluate, loss_and_grads


@pytest.mark.parametrize("act", ["relu", "tanh"])
def test_gradients_match_finite_differences(act):
    rng = np.random.default_rng(0)
    sizes = [5, 7, 6, 3]
    params = {}
    for i in range(3):
        params[f"W{i}"] = rng.normal(size=(sizes[i], sizes[i + 1]))
        params[f"b{i}"] = rng.normal(size=sizes[i + 1]) * 0.1
    X = rng.normal(size=(11, 5))
    y = rng.integers(0, 3, size=11)
    _, grads = loss_and_grads(params, X, y, act)
    eps = 1e-6
    for k, v in params.items():
        for idx in [tuple(rng.integers(0, s) for s in v.shape) for _ in range(5)]:
            old = v[idx]
            v[idx] = old + eps; lp, _ = loss_and_grads(params, X, y, act)
            v[idx] = old - eps; lm, _ = loss_and_grads(params, X, y, act)
            v[idx] = old
            assert grads[k][idx] == pytest.approx((lp - lm) / (2 * eps), rel=1e-4, abs=1e-7)


def test_evaluate_perfect_network():
    # 1-layer net that copies a one-hot input to logits
    params = {"W0": np.eye(3) * 5, "b0": np.zeros(3)}
    X = np.eye(3)
    acc, loss = evaluate(params, X, np.arange(3), "relu")
    assert acc == 1.0 and loss < 0.05
