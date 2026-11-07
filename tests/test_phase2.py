"""Phase 2 families (docs/PHASE2_PLAN.md B.4-B.6, B.10, B.12 #2, #6, #8).

Instance values are read from the task code, never written here: assertions are on booleans so a
failure does not print them either.
"""

import re
from collections import deque
from pathlib import Path

import numpy as np
import pytest

from written_init.agents.prompts import objective_values, prompt_hash, task_prompt
from written_init.experiment import SweepConfig, effective_budgets
from written_init.init_arms import load_weights
from written_init.models import evaluate
from written_init.paths import CONFIGS, INITS, ROOT
from written_init.sandbox import run_build
from written_init.tasks import FAMILIES, family_instances, get_task, spec_task
from written_init.tasks.hidden import (GridNavHidden, connected, draw_parity_subset, draw_ring_radii,
                                       draw_walls, ring_ok)
from written_init.tasks.sparse_parity import RELEVANT as PHASE1_SUBSET

PHASE2 = SweepConfig.load(CONFIGS / "phase2.yaml")


def instances(family):
    return [get_task(t) for t in family_instances(family)]


# ---- B.4 / B.10 blinding -----------------------------------------------------------------------
def _plan_specs() -> dict[str, str]:
    """The B.4 blockquotes of docs/PHASE2_PLAN.md, keyed by family."""
    b4 = (ROOT / "docs" / "PHASE2_PLAN.md").read_text().split("### B.4")[1].split("### B.5")[0]
    out = {}
    for fam, body in re.findall(r"\*\*(\w+)\*\*\n((?:>.*\n)+)", b4):
        out[fam] = "\n".join(line[2:] for line in body.rstrip("\n").split("\n"))
    return out


@pytest.mark.parametrize("family", sorted(FAMILIES))
def test_spec_is_verbatim_from_plan(family):
    assert spec_task(family).task_spec() == _plan_specs()[family]


_NUMBER = re.compile(r"\d+\.\d+")


def _values_in(text: str, task, fixed: frozenset[str] = frozenset()) -> bool:
    """Whether `text` contains this instance's hidden values in any plausible form. Decimal numbers in
    `fixed` are part of the fixed text itself (B.4's bounds, a reference's spec-derived constants): they
    existed before any instance was drawn, so a coincidental match carries no instance information
    (PHASE2_PLAN B.10)."""
    if hasattr(task, "relevant") and task.family == "parity_hidden":
        s = list(task.relevant)
        forms = [", ".join(f"x[{i}]" for i in s), ", ".join(map(str, s)), str(s), str(tuple(s)),
                 "{" + ", ".join(map(str, s)) + "}", " + ".join(f"x[{i}]" for i in s)]
        return any(f in text for f in forms)
    if task.family == "ring_hidden":
        numbers = [n for n in _NUMBER.findall(text) if n not in fixed]
        return any(n.startswith(f"{r:.{k}f}") for n in numbers for r in (task.r_inner, task.r_outer)
                   for k in (2, 3))
    if task.family == "gridnav_hidden":
        w = sorted(task.walls)
        return (str(w) in text or ", ".join(map(str, w)) in text
                or any(f"({v // 9}, {v % 9})" in text for v in w))
    raise AssertionError(task.family)


def _b4_numbers(family) -> frozenset[str]:
    return frozenset(_NUMBER.findall(_plan_specs()[family]))


@pytest.mark.parametrize("family", sorted(FAMILIES))
def test_spec_identical_across_instances_and_free_of_instance_values(family):
    specs = {t.task_spec() for t in instances(family)}
    assert len(specs) == 1
    spec = specs.pop()
    assert frozenset(_NUMBER.findall(spec)) == _b4_numbers(family)
    assert not any(_values_in(spec, t, _b4_numbers(family)) for t in instances(family))


@pytest.mark.parametrize("family", sorted(FAMILIES))
def test_every_prompt_for_a_family_has_one_hash_and_no_instance_values(family):
    prompts = [task_prompt(t, "claude", "noexec", "finetune_family", PHASE2) for t in instances(family)]
    family_prompt = task_prompt(spec_task(family), "claude", "noexec", "finetune_family", PHASE2)
    assert {prompt_hash(p) for p in prompts} == {prompt_hash(family_prompt)}
    assert not any(_values_in(family_prompt, t, _b4_numbers(family)) for t in instances(family))


# The ring reference's constants, all derived from B.4's bounds (B.12 #9): midpoints 0.45 and ~0.732 of
# r_in in [0.10, 0.80] and r_out in [sqrt(0.01 + 0.8/pi), 0.95], inside fraction 0.20-0.50, plus 1.0, 20.0.
RING_REFERENCE_CONSTANTS = {"0.20", "0.50", "0.80", "0.45", "0.8", "0.01", "0.732", "1.0", "20.0"}


def test_reference_inits_contain_no_instance_values():
    for fam in FAMILIES:
        text = "".join(p.read_text() for p in (INITS / fam / "reference").rglob("*") if p.suffix in (".py", ".json"))
        fixed = frozenset()
        if fam == "ring_hidden":
            fixed = _b4_numbers(fam) | RING_REFERENCE_CONSTANTS
            assert set(_NUMBER.findall(text)) <= fixed   # no number that isn't spec-derived
        assert not any(_values_in(text, t, fixed) for t in instances(fam))


# ---- B.6 objective -----------------------------------------------------------------------------
def test_objective_placeholders_equal_the_config():
    text = task_prompt(spec_task("ring_hidden"), "claude", "noexec", "finetune_family", PHASE2)
    assert "{" + ", ".join(str(float(x)) for x in PHASE2.lr) + "}" in text
    assert f"the learning rate chosen from {{{', '.join(map(str, map(float, PHASE2.lr)))}}}" in text
    assert f"the weight decay from {{{', '.join(map(str, map(float, PHASE2.weight_decay)))}}}" in text
    assert f"with AdamW, batch size {PHASE2.batch_size}, for up to {PHASE2.max_steps} steps" in text
    assert PHASE2.optimizer == "adamw" and objective_values(PHASE2)["optimizer"] == "AdamW"
    assert "{" not in text.split("## Goal")[1].split("##")[0].replace(objective_values(PHASE2)["lr_grid"], "") \
        .replace(objective_values(PHASE2)["wd_grid"], "")  # no unfilled placeholder


def test_objective_without_config_is_refused():
    with pytest.raises(ValueError, match="--config"):
        task_prompt(spec_task("ring_hidden"), "claude", "noexec", "finetune_family")


# ---- B.5 instance constraints ------------------------------------------------------------------
def test_instances_are_reproducible():
    for i in range(3):
        assert draw_parity_subset(i) == draw_parity_subset(i)
        assert draw_ring_radii(i) == draw_ring_radii(i)
        assert draw_walls(i) == draw_walls(i)


def test_parity_instances():
    subsets = [tuple(t.relevant) for t in instances("parity_hidden")]
    assert len(subsets) == 6   # i0-i2 (B.5) and i3-i5 (follow-up F1)
    assert all(len(set(s)) == 4 and all(0 <= i < 16 for i in s) for s in subsets)
    assert len(set(subsets)) == 6 and tuple(PHASE1_SUBSET) not in subsets


def test_parity_instances_use_the_b5_seeds():
    """Independent rerun of the B.5 draw with seeds [2026, 11, 4, 1, i], also for F1's i3-i5."""
    taken, ok = [tuple(PHASE1_SUBSET)], True
    for i in range(6):
        rng = np.random.default_rng([2026, 11, 4, 1, i])
        while (s := tuple(sorted(int(v) for v in rng.choice(16, 4, replace=False)))) in taken:
            pass
        taken.append(s)
        ok &= tuple(get_task(f"parity_hidden_i{i}").relevant) == s
    assert ok


def test_f1_config_is_phase2_except_tasks_budgets_and_seeds():
    f1 = SweepConfig.load(CONFIGS / "phase2_parity_f1.yaml")
    assert f1.tasks == ["parity_hidden_i3", "parity_hidden_i4", "parity_hidden_i5"]
    assert f1.budgets == [0, 16, 64, 96, 128, 192, 256, 384, 512, 1024] and f1.seeds == list(range(12))
    rest = lambda c: {k: v for k, v in vars(c).items() if k not in ("tasks", "budgets", "seeds")}
    assert rest(f1) == rest(PHASE2)


def test_parity_split_is_the_phase1_split():
    p1 = get_task("sparse_parity")
    for t in instances("parity_hidden"):
        for split in ("train", "val", "test"):
            assert np.array_equal(t._parts[split][0], p1._parts[split][0])


def test_ring_instances_inside_fraction():
    X = np.random.default_rng(0).uniform(-1, 1, size=(400_000, 2))
    for t in instances("ring_hidden"):
        assert ring_ok(t.r_inner, t.r_outer)
        assert 0.20 <= t.label(X).mean() <= 0.50


def _free_cells_connected(walls) -> bool:
    """Independent flood fill (not the task's BFS)."""
    free = {(r, c) for r in range(9) for c in range(9) if r * 9 + c not in walls}
    start = next(iter(free))
    seen, q = {start}, deque([start])
    while q:
        r, c = q.popleft()
        for n in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
            if n in free and n not in seen:
                seen.add(n)
                q.append(n)
    return seen == free


def test_gridnav_instances_walls_and_connectivity():
    for t in instances("gridnav_hidden"):
        assert 8 <= len(t.walls) <= 12 and all(0 <= v < 81 for v in t.walls)
        assert _free_cells_connected(t.walls)
    assert not connected(frozenset(range(9, 18)))  # a full wall row splits the grid


# ---- gridnav_hidden expert ---------------------------------------------------------------------
def _label(t, a, g):
    (ar, ac), (gr, gc) = a, g
    return int(t.expert(*(np.array([v]) for v in (ar, ac, gr, gc)))[0])


def test_bfs_on_hand_built_walls():
    # Column 4 is a wall except at row 8: going from the left half to the right half means a detour.
    t = GridNavHidden(walls=[r * 9 + 4 for r in range(8)])
    d = t._dist[0 * 9 + 8]                        # distances to the goal (0, 8)
    assert d[0 * 9 + 0] == 8 + 8 + 8              # down to row 8, across, back up
    assert d[0 * 9 + 4] == np.inf                 # wall cell
    assert d[8 * 9 + 4] == 4 + 8                  # the gap: 4 right, 8 up
    assert _label(t, (0, 0), (0, 8)) == 4         # right still begins a shortest path around the wall
    assert _label(t, (0, 3), (0, 8)) == 2         # right is the wall; only down begins a shortest path
    assert _label(t, (8, 3), (0, 8)) == 4         # wall-free says up; the gap lies to the right
    assert _label(t, (5, 5), (5, 5)) == 0


def test_tie_break_order_when_wall_free_move_is_blocked():
    # Agent (4, 4), goal (4, 6), wall at (4, 5): right is blocked; up and down both start a 4-step
    # shortest path, left doesn't. The rule takes the first of right, left, down, up: down.
    t = GridNavHidden(walls=[4 * 9 + 5, 0, 1, 2, 3, 5, 6, 7])
    assert _label(t, (4, 4), (4, 6)) == 2
    # Wall at (3, 6) too: only down remains.
    t2 = GridNavHidden(walls=[4 * 9 + 5, 3 * 9 + 5, 0, 1, 2, 3, 6, 7])
    assert _label(t2, (4, 4), (4, 6)) == 2
    # Block down instead (5, 5): up is the only shortest start.
    t3 = GridNavHidden(walls=[4 * 9 + 5, 5 * 9 + 5, 0, 1, 2, 3, 6, 7])
    assert _label(t3, (4, 4), (4, 6)) == 1


def _independent_dist(walls):
    """All-pairs shortest path lengths by Floyd-Warshall over free cells (independent of the task)."""
    D = np.full((81, 81), np.inf)
    for v in range(81):
        if v in walls:
            continue
        D[v, v] = 0
        r, c = divmod(v, 9)
        for rr, cc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
            u = rr * 9 + cc
            if 0 <= rr < 9 and 0 <= cc < 9 and u not in walls:
                D[v, u] = 1
    for k in range(81):
        D = np.minimum(D, D[:, [k]] + D[[k], :])
    return D


@pytest.mark.parametrize("name", family_instances("gridnav_hidden"))
def test_gridnav_labels_follow_the_spec(name):
    t = get_task(name)
    D = _independent_dist(t.walls)
    moves = {4: (0, 1), 3: (0, -1), 2: (1, 0), 1: (-1, 0)}
    ok = True
    for split in ("train", "val", "test"):
        X, y = t._parts[split]
        a, g = X[:, :81].argmax(1), X[:, 81:].argmax(1)
        ok &= not (set(a) | set(g)) & set(t.walls)   # agents and goals only on free cells
        for ai, gi, yi in zip(a, g, y):
            (ar, ac), (gr, gc) = divmod(int(ai), 9), divmod(int(gi), 9)
            if ai == gi:
                ok &= yi == 0
                continue
            def begins(m):
                rr, cc = ar + moves[m][0], ac + moves[m][1]
                return 0 <= rr < 9 and 0 <= cc < 9 and D[gi, rr * 9 + cc] == D[gi, ai] - 1
            dr, dc = gr - ar, gc - ac
            wf = (4 if dc > 0 else 3) if abs(dc) >= abs(dr) else (2 if dr > 0 else 1)
            expect = wf if begins(wf) else next(m for m in (4, 3, 2, 1) if begins(m))
            ok &= yi == expect
    assert ok


@pytest.mark.parametrize("name", family_instances("gridnav_hidden") + family_instances("parity_hidden"))
def test_phase2_splits_are_disjoint(name):
    t = get_task(name)
    keys = {s: {row.tobytes() for row in t._parts[s][0]} for s in ("train", "val", "test")}
    assert not keys["train"] & keys["test"] and not keys["train"] & keys["val"] and not keys["val"] & keys["test"]
    if t.family == "gridnav_hidden":
        n_free = 81 - len(t.walls)
        assert t.split_size("test") == 1500 and t.split_size("val") == 256
        assert sum(t.split_size(s) for s in keys) == n_free**2


# ---- H9 / references ---------------------------------------------------------------------------
def _accuracy(build: Path, task, tmp_path) -> float:
    ok, msg = run_build(build, tmp_path / "w.npz")
    assert ok, msg
    X, y = task._parts["test"] if hasattr(task, "_parts") else task.sample(2000, np.random.default_rng(0), "test")
    return evaluate(load_weights(task, tmp_path / "w.npz"), X, y, task.activation)[0]


@pytest.mark.parametrize("name", family_instances("parity_hidden"))
def test_phase1_subset_parity_init_is_at_chance_on_every_instance(name, tmp_path):
    t = get_task(name)
    acc = _accuracy(INITS / "sparse_parity" / "reference" / "sample_00" / "build.py", t, tmp_path)
    assert t.split_size("test") == 2000 and abs(acc - 0.5) <= 0.04


@pytest.mark.parametrize("name", family_instances("parity_hidden") + family_instances("gridnav_hidden")
                         + family_instances("ring_hidden"))
def test_family_reference_inits(name, tmp_path):
    t = get_task(name)
    acc = _accuracy(INITS / t.family / "reference" / "sample_00" / "build.py", t, tmp_path)
    if t.family == "parity_hidden":
        assert abs(acc - 0.5) <= 0.04            # all-16-bit parity carries no subset information
    elif t.family == "gridnav_hidden":
        assert acc >= 0.75                       # the wall-free rule (cf. H9's gridnav prediction)


# ---- A.4 pool rule -----------------------------------------------------------------------------
def test_pool_rule():
    default = SweepConfig.load(CONFIGS / "default.yaml").budgets
    assert effective_budgets(get_task("digits8x8"), default) == [0, 16, 64, 256, 1000]
    for t in ("sparse_parity", "ring2d", "gridnav"):     # main_v1 keys for these stay as they were
        assert effective_budgets(get_task(t), default) == default
    for t in instances("gridnav_hidden"):
        b = effective_budgets(t, PHASE2.budgets)
        assert b[:-1] == [0, 16, 64, 256, 1024] and b[-1] == t.max_train_pool < 4096
    assert effective_budgets(get_task("digits8x8"), [16, 1024, 1000, 4096]) == [16, 1000]
