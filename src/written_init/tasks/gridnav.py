"""Grid navigation by behavior cloning.

A 9x9 grid holds an agent and a goal. The label is a scripted expert's action.
This mirrors the small game-policy networks in weight-space-programming work
but uses supervised imitation so no RL is needed.
"""

from __future__ import annotations

import numpy as np

from .base import PartitionedTask

ACTIONS = ["stay", "up", "down", "left", "right"]


class GridNav(PartitionedTask):
    name = "gridnav"
    activation = "relu"

    def __init__(self, size: int = 9, hidden=(64, 64)):
        self.size = size
        self.in_dim = 2 * size * size
        self.out_dim = len(ACTIONS)
        self.hidden = list(hidden)
        # Enumerate all (agent, goal) pairs, then split into disjoint pools.
        g = np.array(np.meshgrid(*[np.arange(size)] * 4, indexing="ij")).reshape(4, -1)
        ar, ac, gr, gc = g
        self._partition(self.encode(ar, ac, gr, gc), self.expert(ar, ac, gr, gc),
                        n_test=1500, n_val=256, split_seed=12345)

    def expert(self, ar, ac, gr, gc) -> np.ndarray:
        """Vectorized expert. Rows grow downward. Ties go horizontal."""
        dr = gr - ar  # row delta (positive = goal is below)
        dc = gc - ac           # col delta (positive = goal is to the right)
        a = np.zeros_like(dr)
        horiz = (np.abs(dc) >= np.abs(dr)) & (dc != 0)
        vert = (np.abs(dr) > np.abs(dc))
        a[horiz & (dc > 0)] = 4  # right
        a[horiz & (dc < 0)] = 3  # left
        a[vert & (dr > 0)] = 2   # down
        a[vert & (dr < 0)] = 1   # up
        return a.astype(np.int64)

    def encode(self, ar, ac, gr, gc) -> np.ndarray:
        n = len(ar)
        cells = self.size * self.size
        X = np.zeros((n, 2 * cells))
        X[np.arange(n), ar * self.size + ac] = 1.0
        X[np.arange(n), cells + gr * self.size + gc] = 1.0
        return X

    def task_spec(self) -> str:
        s = self.size
        c = s * s
        return (
            f"A {s}x{s} grid with rows r = 0..{s - 1} (row 0 at the top, rows increase downward) "
            f"and columns c = 0..{s - 1} (column 0 at the left).\n"
            f"Input: a vector x of length {2 * c}. x[0:{c}] is a one-hot encoding of the agent's cell, "
            f"with the agent at (r, c) setting x[r*{s} + c] = 1. x[{c}:{2 * c}] is a one-hot encoding "
            f"of the goal's cell, with the goal at (r, c) setting x[{c} + r*{s} + c] = 1. "
            "Agent and goal positions are independent and uniform over the grid; they can coincide.\n"
            "Label: the action of a scripted expert. Let dr = goal_row - agent_row and "
            "dc = goal_col - agent_col.\n"
            "  - if dr == 0 and dc == 0: action 0 (stay)\n"
            "  - else if |dc| >= |dr|: move horizontally toward the goal: action 4 (right) if dc > 0, "
            "action 3 (left) if dc < 0\n"
            "  - else: move vertically toward the goal: action 2 (down) if dr > 0, action 1 (up) if dr < 0\n"
            "Classes: 0 = stay, 1 = up, 2 = down, 3 = left, 4 = right."
        )
