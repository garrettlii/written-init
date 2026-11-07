import numpy as np
import pytest

from written_init.metrics import equivalent_n, monotone, multiplier, resolve

B = np.array([16, 64, 256, 1024])
A = np.array([0.5, 0.6, 0.7, 0.8])  # +0.1 accuracy per 4x data


def test_exact_on_grid_and_interpolated():
    assert equivalent_n(B, A, 0.7) == (pytest.approx(256), "")
    n_eq, c = equivalent_n(B, A, 0.65)  # halfway in log space between 64 and 256
    assert c == "" and n_eq == pytest.approx(128)
    m, _ = multiplier(B, A, 16, 0.7)
    assert m == pytest.approx(16)


def test_censoring():
    assert equivalent_n(B, A, 0.9) == (1024, ">")
    assert equivalent_n(B, A, 0.4) == (16, "<")


def test_monotone_envelope():
    _, a = monotone(B, np.array([0.5, 0.7, 0.65, 0.8]))
    assert list(a) == [0.5, 0.7, 0.7, 0.8]


# ---- resolve(): the v0.3 rules -------------------------------------------------

PARITY_B = [16, 64, 128, 1024]
PARITY_A = [0.499, 0.491, 0.504, 0.995]  # flat at chance, then a jump (the smoke run)
H0 = [0.005] * 4


def test_chance_gets_no_multiplier():
    # The smoke-run artifact: shuffled at ~0.50 used to be "worth ~109 examples".
    r = resolve(PARITY_B, PARITY_A, H0, acc=0.503, acc_ci_half=0.004, chance=0.5)
    assert r["status"] == "chance" and r["n_eq"] is None


def test_chance_margin_widens_with_arm_ci():
    r = resolve(PARITY_B, PARITY_A, H0, acc=0.53, acc_ci_half=0.05, chance=0.5)
    assert r["status"] == "chance"


def test_point_inside_a_jump_keeps_its_bracket():
    r = resolve(PARITY_B, PARITY_A, H0, acc=0.9, acc_ci_half=0.01, chance=0.5)
    assert r["status"] == "point" and (r["lo"], r["hi"]) == (128, 1024)
    assert 128 < r["n_eq"] < 1024


def test_flat_segment_above_chance_is_a_range():
    b, a = [16, 64, 256, 1024], [0.70, 0.80, 0.81, 0.95]
    r = resolve(b, a, [0.002] * 4, acc=0.805, acc_ci_half=0.002, chance=0.5)
    assert r["status"] == "range" and (r["lo"], r["hi"]) == (64, 256) and r["n_eq"] is None


def test_wide_random_ci_also_makes_a_range():
    b, a = [16, 64], [0.70, 0.75]
    r = resolve(b, a, [0.01, 0.08], acc=0.72, acc_ci_half=0.0, chance=0.5)
    assert r["status"] == "range"


def test_bounds_outside_measured_range():
    assert resolve(B, A, [0.0] * 4, acc=0.95, acc_ci_half=0.0, chance=0.3)["status"] == "above"
    assert resolve(B, A, [0.0] * 4, acc=0.45, acc_ci_half=0.0, chance=0.3)["status"] == "below"


def test_matches_old_metric_when_curve_is_clean():
    r = resolve(B, A, [0.0] * 4, acc=0.65, acc_ci_half=0.0, chance=0.3)
    assert r["status"] == "point" and r["n_eq"] == pytest.approx(128)


def test_stratified_mean_ci_weights_groups_equally():
    from written_init.metrics import stratified_mean_ci
    m, lo, hi = stratified_mean_ci([np.array([1.0, 1.0, 1.0, 1.0]), np.array([0.0])])
    assert m == 0.5 and lo == hi == 0.5          # constant groups: no spread, equal weight despite sizes
    m, lo, hi = stratified_mean_ci([np.array([0.0, 1.0]), np.array([2.0, 2.0])])
    assert m == 1.25 and 1.0 <= lo < m < hi <= 1.5  # only the first group varies: CI within its range / 2


def test_samples_to_target_and_ratio():
    from written_init.metrics import samples_to_target, target_ratio
    b = [0, 16, 64, 256]
    assert samples_to_target(b, [0.96, 0.9, 0.97, 0.99], 0.95) == (0.0, "")    # zero-shot already there
    assert samples_to_target(b, [0.5, 0.96, 0.97, 0.99], 0.95) == (16.0, "<=")  # first met between 0 and 16
    assert samples_to_target(b, [0.5, 0.6, 0.7, 0.8], 0.95) == (256.0, ">")     # never met
    n, c = samples_to_target(b, [0.5, 0.6, 0.8, 1.0], 0.9)                       # halfway from 64 to 256 in log
    assert c == "" and np.isclose(n, 128.0)
    n, c = samples_to_target(b, [0.5, 0.6, 0.9, 0.85], 0.9)                      # running max: met at 64
    assert c == "" and np.isclose(n, 64.0)
    assert target_ratio((128.0, ""), (16.0, "")) == (8.0, "")
    assert target_ratio((256.0, ">"), (16.0, "<=")) == (16.0, ">=")
    assert target_ratio((16.0, "<="), (64.0, "")) == (0.25, "<=")
    assert target_ratio((256.0, ">"), (256.0, ">")) == (None, "undetermined")
    assert target_ratio((64.0, ""), (0.0, "")) == (None, "not defined")
