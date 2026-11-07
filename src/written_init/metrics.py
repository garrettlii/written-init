"""Data-multiplier metric.

For an arm that reaches mean test accuracy `a` with `n` training examples, the
equivalent random-init data n_eq is how many examples the random arm needs to
reach `a`, read off the random arm's accuracy-vs-budget curve by linear
interpolation in log(budget). The multiplier is n_eq / n.

The random curve is made monotone (running max) first, so noise cannot create
multiple crossings. Values outside the measured range are censored:
  ">"  arm beats random's best measured budget: multiplier is a lower bound
  "<"  arm is below random's smallest budget: multiplier is an upper bound
For budget 0 (zero-shot) there is no multiplier; n_eq alone answers "how many
examples is this init worth before any training?"

`resolve` (v0.3) is what the analysis reports. It refuses to turn noise into a
number, in this order:
  chance       arm accuracy within the margin of a constant majority-class
               predictor: no multiplier at all
  below/above  outside random's measured range: a bound, as before
  range        the bracketing segment of random's curve rises less than the
               margin (flat, e.g. parity before its jump): n_eq is only known
               to lie between the two budgets, so report that interval
  point        interpolated estimate, always reported WITH its bracket, since
               log-linear interpolation inside a sudden jump is an assumption
The margin is max(--margin, the relevant 95% CI half-width).
"""

from __future__ import annotations

import numpy as np


def monotone(budgets: np.ndarray, accs: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    order = np.argsort(budgets)
    b = np.asarray(budgets, dtype=float)[order]
    a = np.maximum.accumulate(np.asarray(accs, dtype=float)[order])
    return b, a


def equivalent_n(rand_budgets, rand_accs, acc: float) -> tuple[float, str]:
    """Return (n_eq, censor) with censor in {"", ">", "<"}. Budgets must be > 0."""
    b, a = monotone(np.asarray(rand_budgets), np.asarray(rand_accs))
    if acc <= a[0]:
        return float(b[0]), "<"
    if acc > a[-1]:
        return float(b[-1]), ">"
    j = int(np.argmax(a >= acc))  # first budget reaching acc; j >= 1 here
    lb0, lb1 = np.log(b[j - 1]), np.log(b[j])
    t = (acc - a[j - 1]) / (a[j] - a[j - 1])
    return float(np.exp(lb0 + t * (lb1 - lb0))), ""


def multiplier(rand_budgets, rand_accs, n: int, acc: float) -> tuple[float, str]:
    n_eq, c = equivalent_n(rand_budgets, rand_accs, acc)
    return n_eq / n, c


def bootstrap_multiplier(rand_by_budget: dict[int, np.ndarray], arm_accs: np.ndarray, n: int,
                         n_boot: int = 2000, seed: int = 0) -> tuple[float, float]:
    """95% percentile CI for the multiplier (or n_eq if n == 0), resampling seeds
    independently within each budget of the random arm and within the arm."""
    r = np.random.default_rng(seed)
    budgets = np.array(sorted(b for b in rand_by_budget if b > 0))
    out = np.empty(n_boot)
    for i in range(n_boot):
        ra = np.array([r.choice(rand_by_budget[b], size=len(rand_by_budget[b])).mean() for b in budgets])
        aa = r.choice(arm_accs, size=len(arm_accs)).mean()
        n_eq, _ = equivalent_n(budgets, ra, aa)
        out[i] = n_eq / n if n > 0 else n_eq
    lo, hi = np.percentile(out, [2.5, 97.5])
    return float(lo), float(hi)


def mean_ci(x: np.ndarray, n_boot: int = 2000, seed: int = 0) -> tuple[float, float, float]:
    x = np.asarray(x, dtype=float)
    if len(x) == 1:
        return float(x[0]), float(x[0]), float(x[0])
    r = np.random.default_rng(seed)
    boots = r.choice(x, size=(n_boot, len(x))).mean(axis=1)
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return float(x.mean()), float(lo), float(hi)


def resolve(rand_budgets, rand_means, rand_ci_half, acc: float, acc_ci_half: float, chance: float,
            margin: float = 0.02) -> dict:
    """Classify and estimate n_eq for one arm/budget cell. See module docstring.

    rand_ci_half: 95% CI half-width of the random arm's mean at each budget.
    Returns {"status", "n_eq", "lo", "hi"} with n_eq None unless status == "point".
    """
    b = np.asarray(rand_budgets, dtype=float)
    order = np.argsort(b)
    b = b[order]
    a = np.maximum.accumulate(np.asarray(rand_means, dtype=float)[order])
    h = np.asarray(rand_ci_half, dtype=float)[order]

    if acc <= chance + max(margin, acc_ci_half):
        return {"status": "chance", "n_eq": None, "lo": None, "hi": None}
    if acc <= a[0]:
        return {"status": "below", "n_eq": None, "lo": None, "hi": float(b[0])}
    if acc > a[-1]:
        return {"status": "above", "n_eq": None, "lo": float(b[-1]), "hi": None}
    j = int(np.argmax(a >= acc))
    lo, hi = float(b[j - 1]), float(b[j])
    if a[j] - a[j - 1] < max(margin, h[j - 1], h[j]):
        return {"status": "range", "n_eq": None, "lo": lo, "hi": hi}
    n_eq, _ = equivalent_n(b, a, acc)
    return {"status": "point", "n_eq": n_eq, "lo": lo, "hi": hi}


def stratified_mean_ci(groups: list[np.ndarray], n_boot: int = 2000, seed: int = 0) -> tuple[float, float, float]:
    """Mean over groups of each group's mean, with a 95% percentile CI from a bootstrap that resamples
    within each group (PHASE2_PLAN B.8: seeds within each instance, instances weighted equally)."""
    groups = [np.asarray(g, dtype=float) for g in groups]
    r = np.random.default_rng(seed)
    point = float(np.mean([g.mean() for g in groups]))
    boots = np.mean([r.choice(g, size=(n_boot, len(g))).mean(axis=1) for g in groups], axis=0)
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return point, float(lo), float(hi)


def samples_to_target(budgets, accs, target: float) -> tuple[float, str]:
    """Examples an arm needs for its mean test accuracy to reach `target` (PHASE2_PLAN B.8), read off
    its own running-max curve by log-linear interpolation. Returns (n, censor): "" exact, "<=" reached
    by the smallest positive budget, ">" not reached by the largest. n = 0 if zero-shot meets it."""
    b, a = monotone(budgets, accs)
    if b[0] == 0:
        if a[0] >= target:
            return 0.0, ""
        b, a = b[1:], a[1:]
    n, c = equivalent_n(b, a, target)
    return n, {"<": "<=", ">": ">", "": ""}[c]


def target_ratio(rand: tuple[float, str], arm: tuple[float, str]) -> tuple[float | None, str]:
    """random / arm samples-to-target, carrying censoring: (value, kind), kind in
    {"", ">=", "<=", "undetermined", "not defined"} ("not defined": the arm needs no data)."""
    (rn, rc), (wn, wc) = rand, arm
    if wn == 0:
        return None, "not defined"
    v = rn / wn
    if rc == "" and wc == "":
        return v, ""
    if rc in ("", ">") and wc in ("", "<="):   # random at least rn, arm at most wn
        return v, ">="
    if rc in ("", "<=") and wc in ("", ">"):   # random at most rn, arm at least wn
        return v, "<="
    return None, "undetermined"
