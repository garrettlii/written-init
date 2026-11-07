"""2D annulus classification: is the point inside a ring?

Needs a curved decision boundary from piecewise-linear units. Medium
writability: the rule is simple, but encoding r^2 with ReLUs takes some craft.
"""

from __future__ import annotations

import numpy as np

from .base import Task


class Ring2D(Task):
    name = "ring2d"
    activation = "relu"

    def __init__(self, r_inner: float = 0.4, r_outer: float = 0.75, hidden=(32, 32)):
        self.r_inner = r_inner
        self.r_outer = r_outer
        self.in_dim = 2
        self.out_dim = 2
        self.hidden = list(hidden)

    def label(self, X: np.ndarray) -> np.ndarray:
        r = np.sqrt((X**2).sum(axis=1))
        return ((r >= self.r_inner) & (r <= self.r_outer)).astype(np.int64)

    def sample(self, n, rng, split):
        X = rng.uniform(-1.0, 1.0, size=(n, 2))
        return X, self.label(X)

    def task_spec(self) -> str:
        return (
            "Input: a point (x[0], x[1]) drawn uniformly from the square [-1, 1] x [-1, 1].\n"
            f"Label: 1 if the point lies inside the ring {self.r_inner} <= sqrt(x[0]^2 + x[1]^2) "
            f"<= {self.r_outer}, else 0.\n"
            "Classes: 0 = outside the ring, 1 = inside the ring. "
            "(About 32% of points are inside.)"
        )
