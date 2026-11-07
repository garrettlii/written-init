"""The v0.3 control arms, including the dead-unit problem that motivated them."""

import numpy as np
import pytest

from written_init.experiment import Arm, build_init
from written_init.init_arms import add_noise, load_weights, norm_matched, shuffle_within_tensors
from written_init.paths import INITS
from written_init.sandbox import run_build
from written_init.tasks import get_task


@pytest.fixture(scope="module")
def parity_ref():
    """Build the (gitignored) reference weights if needed; build_init reads them from inits/."""
    d = INITS / "sparse_parity" / "reference" / "sample_00"
    if not (d / "weights.npz").exists():
        ok, msg = run_build(d / "build.py", d / "weights.npz")
        assert ok, msg
    return load_weights(get_task("sparse_parity"), d / "weights.npz")


def _alive(params) -> tuple[float, float]:
    """Share of layer-1 and layer-2 ReLU units positive on at least one of 512 train inputs.
    A unit that is never positive gets zero gradient, so it never updates."""
    X, _ = get_task("sparse_parity").sample(512, np.random.default_rng(0), "train")
    h1 = np.maximum(X @ params["W0"] + params["b0"], 0)
    h2 = np.maximum(h1 @ params["W1"] + params["b1"], 0)
    return float((h1 > 0).any(axis=0).mean()), float((h2 > 0).any(axis=0).mean())


def test_norm_matched_keeps_norms_and_zeros(parity_ref):
    nm = norm_matched(parity_ref, np.random.default_rng(1))
    for k, v in parity_ref.items():
        assert np.linalg.norm(nm[k]) == pytest.approx(np.linalg.norm(v))
        if np.linalg.norm(v) == 0:
            assert not nm[k].any()
    # dense, unlike the written weights
    assert (nm["W0"] != 0).mean() > 0.99 and (parity_ref["W0"] != 0).mean() < 0.05


@pytest.mark.parametrize("seed", range(5))
def test_shuffled_is_mostly_dead_and_shuffled_noise_is_not(parity_ref, seed):
    """Why plain `shuffled` is only a secondary control (see init_arms docstring).
    Measured in v0.3: shuffled keeps 0-6% of layer-2 units alive; with noise, 97-100%."""
    task = get_task("sparse_parity")
    shuffled = shuffle_within_tensors(parity_ref, np.random.default_rng(seed))
    revived = add_noise(task, shuffled, 0.1, np.random.default_rng(100 + seed))
    assert _alive(shuffled)[1] <= 0.10
    assert min(_alive(revived)) >= 0.80


def test_build_init_new_kinds_are_deterministic_and_paired(parity_ref):
    task = get_task("sparse_parity")
    for kind in ["shuffled_noise", "norm_matched"]:
        arm = Arm(kind, kind, source="reference")
        p1, sid1 = build_init(task, arm, seed=3)
        p2, sid2 = build_init(task, arm, seed=3)
        p3, _ = build_init(task, arm, seed=4)
        assert sid1 == sid2 == "sample_00"
        assert all(np.array_equal(p1[k], p2[k]) for k in p1)
        assert not all(np.array_equal(p1[k], p3[k]) for k in p1)


def test_shuffled_noise_uses_the_same_noise_scale_as_written_noise(parity_ref):
    task = get_task("sparse_parity")
    wn, _ = build_init(task, Arm("wn", "written_noise", source="reference", alpha=0.1), seed=0)
    sn, _ = build_init(task, Arm("sn", "shuffled_noise", source="reference", alpha=0.1), seed=0)
    # Noise std on W0 (written part removed) should match: written values are 0/1, so compare
    # the spread of entries that were zero in both before noise.
    zero_w = parity_ref["W0"] == 0
    assert np.std(wn["W0"][zero_w]) == pytest.approx(np.std(sn["W0"][np.abs(sn["W0"]) < 0.5]), rel=0.2)
