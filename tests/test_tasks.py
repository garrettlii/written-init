import numpy as np
import pytest

from written_init.tasks import get_task, task_names


@pytest.mark.parametrize("name", task_names())
def test_shapes_and_spec(name):
    t = get_task(name)
    X, y = t.sample(8, np.random.default_rng(0), "train")
    assert X.shape == (8, t.in_dim) and y.shape == (8,)
    assert y.min() >= 0 and y.max() < t.out_dim
    spec = t.task_spec() + t.arch_spec()
    for k, shape in t.param_shapes().items():
        assert f"{k}: {shape}" in spec


@pytest.mark.parametrize("name", ["sparse_parity", "gridnav", "digits8x8"])
def test_partitions_are_disjoint(name):
    t = get_task(name)
    keys = {}
    for split in ["train", "val", "test"]:
        X, _ = t._parts[split]
        keys[split] = {row.tobytes() for row in X}
    if name == "digits8x8":  # real data may contain duplicate images; just check sizes
        assert sum(len(t._parts[s][1]) for s in keys) == 1797
        return
    assert not keys["train"] & keys["test"]
    assert not keys["train"] & keys["val"]
    assert not keys["val"] & keys["test"]


def test_gridnav_expert_cases():
    t = get_task("gridnav")
    a = lambda ar, ac, gr, gc: int(t.expert(np.array([ar]), np.array([ac]), np.array([gr]), np.array([gc]))[0])
    assert a(4, 4, 4, 4) == 0  # at goal: stay
    assert a(4, 4, 0, 4) == 1  # goal above: up
    assert a(4, 4, 8, 4) == 2  # goal below: down
    assert a(4, 4, 4, 0) == 3  # goal left: left
    assert a(4, 4, 4, 8) == 4  # goal right: right
    assert a(4, 4, 6, 6) == 4  # tie |dr| == |dc|: horizontal
    assert a(4, 4, 7, 5) == 2  # |dr| > |dc|: vertical


def test_sparse_parity_labels():
    t = get_task("sparse_parity")
    X = np.zeros((2, 16)); X[1, list(t.relevant)[:3]] = 1
    assert list(t.label(X)) == [0, 1]
