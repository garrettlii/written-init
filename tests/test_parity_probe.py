"""scripts/parity_gradient_probe.py (follow-up F1c) on hand-built networks with exact answers."""

import importlib.util
from pathlib import Path

import numpy as np
import pytest

from written_init.experiment import SweepConfig, build_init
from written_init.init_arms import load_weights, written_samples
from written_init.paths import CONFIGS
from written_init.tasks import get_task
from written_init.tasks.sparse_parity import SparseParity

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("parity_gradient_probe", ROOT / "scripts" / "parity_gradient_probe.py")
probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(probe)
S = (3, 7, 8, 12)


def _one_bit_net(w: float) -> dict:
    """16 -> 2 -> 2 relu net reading only bit 3 with weight w (both units always active)."""
    W0 = np.zeros((16, 2))
    W0[3, 0] = w
    return {"W0": W0, "b0": np.ones(2), "W1": np.array([[1.0, -1.0], [0.0, 0.0]]), "b1": np.array([-1.5, 1.5])}


def _two_of_three_net(triples) -> dict:
    """Unit k is on when at least 2 of the 3 bits in triples[k] are set, and votes for class 0. Its gate
    correlates with the parity of those 3 bits, so with S's labels its label gradient falls only on
    the 4th bit of S, and nowhere when the triple is not 3 bits of S."""
    W0 = np.zeros((16, len(triples)))
    for k, t in enumerate(triples):
        W0[list(t), k] = 1.0
    return {"W0": W0, "b0": np.full(len(triples), -1.5), "W1": np.tile([1.0, -1.0], (len(triples), 1)),
            "b1": np.zeros(2)}


@pytest.mark.parametrize("net,relevant", [
    (_one_bit_net(1.0), S),                      # gradient sits on bit 3, but none of it depends on the labels
    (_one_bit_net(0.0), S),                      # constant network
    (_two_of_three_net([(3, 7, 8)]), (0, 1, 2, 12)),
])
def test_no_label_signal(net, relevant):
    r = probe.probe(net, SparseParity(relevant=relevant))
    assert not r["label_signal"] and r["share"] is None and r["rank"] is None and r["norm_D"] < 1e-12


def test_label_gradient_points_at_the_missing_bit():
    r = probe.probe(_two_of_three_net([(3, 7, 8)]), SparseParity(relevant=S))
    assert r["label_signal"] and r["share"] == pytest.approx(1.0, abs=1e-12) and r["ratio"] > 0
    assert r["rank"] == 455   # all on bit 12: every subset containing it (C(15, 3)) ties, and ties count against S
    assert r["norm_D"] == pytest.approx(1 / 8, abs=1e-12)   # -c/4 * (E[chi_S g] - E[chi_T g]) = -2/4 * (0 - 1/4)


def test_subset_ranks_first_when_every_relevant_row_gets_label_signal():
    r = probe.probe(_two_of_three_net([(7, 8, 12), (3, 8, 12), (3, 7, 12), (3, 7, 8)]), SparseParity(relevant=S))
    assert r["share"] == pytest.approx(1.0, abs=1e-12) and r["rank"] == 1
    assert r["norm_D"] == pytest.approx(1 / 4, abs=1e-12)   # 1/8 on each of the 4 rows


def test_ranks_over_all_subsets():
    # The unit on (3, 7, 8) carries label signal only for the 13 subsets containing all three, each
    # with all of it on the 4th bit (rank 455 as above).
    ranks = probe.ranks_over_all_subsets(_two_of_three_net([(3, 7, 8)]))
    with_signal = [r for r, s in zip(ranks, probe.SUBSETS) if r is not None]
    assert len(ranks) == 1820 and with_signal == [455] * 13
    assert all(r is not None for r, s in zip(ranks, probe.SUBSETS) if {3, 7, 8} <= set(s))


def test_baselines_are_the_sweep_arms_inits():
    cfg = SweepConfig.load(CONFIGS / "phase2_parity_f1.yaml")
    t = get_task("parity_hidden_i3")
    written = {f.parent.name: load_weights(t, f) for f in written_samples("parity_hidden", probe.SOURCE, True)}
    mine = {(k, sid, s): p for k, sid, s, p in probe.baseline_inits(t, written, cfg)}
    arms = {a.kind: a for a in cfg.arms}
    ok = True
    for s in range(6):   # the sweep gives seed s to sample s % 3
        for kind in ("random", "norm_matched", "shuffled_noise"):
            ref, sid = build_init(t, arms[kind], s, require_audited=True)
            ok &= all(np.array_equal(ref[k], mine[(kind, sid or "-", s)][k]) for k in ref)
    assert ok and len(mine) == 20 + 2 * 6 * len(written)
