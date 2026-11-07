"""Sparse parity: label = XOR of k fixed input bits out of n.

Famously slow for SGD from random init at small data, trivial to write by hand
once you know which bits matter. This is the "high writability" end of the
task suite.
"""

from __future__ import annotations

import numpy as np

from .base import PartitionedTask

RELEVANT = (1, 5, 9, 14)


class SparseParity(PartitionedTask):
    name = "sparse_parity"
    activation = "relu"

    def __init__(self, n_bits: int = 16, relevant: tuple[int, ...] = RELEVANT, hidden=(64, 64)):
        self.n_bits = n_bits
        self.relevant = tuple(relevant)
        self.in_dim = n_bits
        self.out_dim = 2
        self.hidden = list(hidden)
        # Enumerate all 2^n inputs, then split into disjoint test/val/train pools.
        X = ((np.arange(2**n_bits)[:, None] >> np.arange(n_bits)) & 1).astype(np.float64)
        self._partition(X, self.label(X), n_test=2000, n_val=256, split_seed=12345)

    def label(self, X: np.ndarray) -> np.ndarray:
        return (X[:, list(self.relevant)].sum(axis=1) % 2).astype(np.int64)

    def task_spec(self) -> str:
        idx = ", ".join(f"x[{i}]" for i in self.relevant)
        plus = " + ".join(f"x[{i}]" for i in self.relevant)
        return (
            f"Input: {self.n_bits} binary values x[0], ..., x[{self.n_bits - 1}], each 0.0 or 1.0, "
            "drawn independently and uniformly at random.\n"
            f"Label: the parity (XOR) of the {len(self.relevant)} bits {idx}, i.e. "
            f"y = ({plus}) mod 2. All other bits are irrelevant distractors.\n"
            "Classes: 0 = even parity, 1 = odd parity."
        )
