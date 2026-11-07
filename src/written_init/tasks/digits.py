"""8x8 handwritten digits (scikit-learn's bundled copy of the UCI dataset).

The "low writability" control: the label depends on visual knowledge the LLM
can only bring from pretraining. The dataset is small (1,797 images), so the
train pool is capped and budgets above it are skipped.
"""

from __future__ import annotations

import numpy as np

from .base import PartitionedTask

_N_TEST = 597
_N_VAL = 200


class Digits8x8(PartitionedTask):
    name = "digits8x8"
    activation = "relu"

    def __init__(self, hidden=(64, 32), split_seed: int = 12345):
        from sklearn.datasets import load_digits

        d = load_digits()
        X = d.data.astype(np.float64) / 16.0
        y = d.target.astype(np.int64)
        self._partition(X, y, n_test=_N_TEST, n_val=_N_VAL, split_seed=split_seed)
        self.in_dim = 64
        self.out_dim = 10
        self.hidden = list(hidden)

    def task_spec(self) -> str:
        return (
            "Input: an 8x8 grayscale image of a handwritten digit, from the UCI 'Optical Recognition "
            "of Handwritten Digits' dataset (the version bundled with scikit-learn as load_digits). "
            "x has length 64 in row-major order: x[r*8 + c] is the pixel at row r (0 = top) and "
            "column c (0 = left). Each value is the original 0-16 count divided by 16, so it lies in "
            "[0, 1]; ink (the pen stroke) is HIGH, background is 0. Digits are roughly centered "
            "and size-normalized.\n"
            "Label: the digit shown.\n"
            "Classes: 0-9, the digit itself."
        )
