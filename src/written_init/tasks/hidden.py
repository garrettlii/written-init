"""Phase 2 partial-spec families (docs/PHASE2_PLAN.md, B.3-B.5).

The agent is told the family but not the instance. Each family has 3 instances (parity_hidden 6,
after follow-up F1) whose hidden parameters are drawn with
numpy.random.default_rng([2026, 11, 4, family_index, i]) by rejection sampling. The spec text an
agent sees (task_spec) is the same for every instance and contains no instance value. Instance
values exist only in this code and in results: never print them into prompts/, inits/ or anything
an agent reads.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable

import numpy as np

from .gridnav import GridNav
from .ring2d import Ring2D
from .sparse_parity import RELEVANT as PHASE1_SUBSET
from .sparse_parity import SparseParity

# parity_hidden i3-i5: follow-up F1 (docs/PHASE2_PLAN.md Amendments), same B.5 draw.
N_INSTANCES = {"parity_hidden": 6, "ring_hidden": 3, "gridnav_hidden": 3}
SIZE = 9  # gridnav_hidden grid side

# B.4, verbatim.
PARITY_SPEC = (
    "Input: 16 binary values x[0], ..., x[15], each 0.0 or 1.0, drawn independently and uniformly at random.\n"
    "Label: the parity (XOR) of exactly 4 of the 16 bits; the other 12 bits are irrelevant distractors. "
    "Which 4 bits is not given to you. It is fixed within an instance of the task, differs between "
    "instances, and every set of 4 bits is possible.\n"
    "Classes: 0 = even parity, 1 = odd parity."
)
RING_SPEC = (
    "Input: a point (x[0], x[1]) drawn uniformly from the square [-1, 1] x [-1, 1].\n"
    "Label: 1 if the point lies inside a ring centered at the origin, "
    "r_in <= sqrt(x[0]^2 + x[1]^2) <= r_out, else 0. The radii r_in and r_out are not given to you. "
    "They are fixed within an instance of the task and differ between instances. You can rely on: "
    "0.10 <= r_in < r_out <= 0.95, r_out - r_in >= 0.15, and between 20% and 50% of points lie inside "
    "the ring.\n"
    "Classes: 0 = outside the ring, 1 = inside the ring."
)
GRIDNAV_SPEC = (
    "A 9x9 grid with rows r = 0..8 (row 0 at the top, rows increase downward) and columns c = 0..8 "
    "(column 0 at the left). Some cells are walls: between 8 and 12 of the 81 cells, placed so that all "
    "non-wall cells are connected through up, down, left and right moves. Which cells are walls is not "
    "given to you. It is fixed within an instance of the task and differs between instances.\n"
    "Input: a vector x of length 162. x[0:81] is a one-hot encoding of the agent's cell, with the agent "
    "at (r, c) setting x[r*9 + c] = 1. x[81:162] is a one-hot encoding of the goal's cell, with the goal "
    "at (r, c) setting x[81 + r*9 + c] = 1. Agent and goal are on non-wall cells, independent and uniform "
    "over them; they can coincide.\n"
    "Label: the first move of a scripted expert that walks a shortest path from the agent to the goal, "
    "one cell up, down, left or right per step, never into a wall or off the grid. Let "
    "dr = goal_row - agent_row and dc = goal_col - agent_col.\n"
    "  - if dr == 0 and dc == 0: action 0 (stay)\n"
    "  - otherwise, among the moves that begin some shortest path, the expert takes the move the "
    "wall-free rule would take, if it is one of them. The wall-free rule: if |dc| >= |dr|, right (4) when "
    "dc > 0 or left (3) when dc < 0; otherwise down (2) when dr > 0 or up (1) when dr < 0.\n"
    "  - if the wall-free move does not begin a shortest path, the expert takes the first of right (4), "
    "left (3), down (2), up (1) that does.\n"
    "Classes: 0 = stay, 1 = up, 2 = down, 3 = left, 4 = right."
)


def _rng(family_index: int, i: int) -> np.random.Generator:
    return np.random.default_rng([2026, 11, 4, family_index, i])


# ---- instance draws (B.5) ----------------------------------------------------------------------
def draw_parity_subset(i: int) -> tuple[int, ...]:
    earlier = [draw_parity_subset(j) for j in range(i)]
    rng = _rng(1, i)
    while True:
        s = tuple(sorted(int(v) for v in rng.choice(16, 4, replace=False)))
        if s != tuple(PHASE1_SUBSET) and s not in earlier:
            return s


def ring_ok(r_in: float, r_out: float) -> bool:
    inside = np.pi * (r_out**2 - r_in**2) / 4  # ring lies inside the square since r_out < 1
    return 0.10 <= r_in < r_out <= 0.95 and r_out - r_in >= 0.15 and 0.20 <= inside <= 0.50


def draw_ring_radii(i: int) -> tuple[float, float]:
    rng = _rng(2, i)
    while True:
        r_in, r_out = (float(v) for v in rng.uniform(0.10, 0.95, 2))
        if ring_ok(r_in, r_out):
            return r_in, r_out


def bfs(walls: frozenset[int], start: int, size: int = SIZE) -> np.ndarray:
    """Moves from `start` to every cell (inf for walls and unreachable cells)."""
    d = np.full(size * size, np.inf)
    d[start] = 0
    q = deque([start])
    while q:
        u = q.popleft()
        r, c = divmod(u, size)
        for rr, cc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
            v = rr * size + cc
            if 0 <= rr < size and 0 <= cc < size and v not in walls and d[v] == np.inf:
                d[v] = d[u] + 1
                q.append(v)
    return d


def connected(walls: frozenset[int], size: int = SIZE) -> bool:
    free = [v for v in range(size * size) if v not in walls]
    return bool(free) and bool(np.isfinite(bfs(walls, free[0], size)[free]).all())


def draw_walls(i: int) -> frozenset[int]:
    rng = _rng(3, i)
    while True:
        n = int(rng.integers(8, 13))
        walls = frozenset(int(v) for v in rng.choice(SIZE * SIZE, n, replace=False))
        if connected(walls):
            return walls


# ---- families ----------------------------------------------------------------------------------
class ParityHidden(SparseParity):
    family = "parity_hidden"

    def __init__(self, instance: int):
        # Same enumeration and split (seed 12345) as sparse_parity; only the labels change.
        super().__init__(relevant=draw_parity_subset(instance))
        self.instance = instance
        self.name = f"{self.family}_i{instance}"

    def task_spec(self) -> str:
        return PARITY_SPEC


class RingHidden(Ring2D):
    family = "ring_hidden"

    def __init__(self, instance: int):
        super().__init__(*draw_ring_radii(instance))
        self.instance = instance
        self.name = f"{self.family}_i{instance}"

    def task_spec(self) -> str:
        return RING_SPEC


class GridNavHidden(GridNav):
    family = "gridnav_hidden"

    def __init__(self, instance: int | None = None, walls: Iterable[int] | None = None):
        """An instance (walls drawn as in B.5), or explicit `walls` for tests."""
        self.size = SIZE
        self.in_dim = 2 * SIZE * SIZE
        self.out_dim = 5
        self.hidden = [64, 64]
        self.instance = instance
        self.name = f"{self.family}_i{instance}" if walls is None else f"{self.family}_custom"
        self.walls = draw_walls(instance) if walls is None else frozenset(walls)
        if not connected(self.walls):
            raise ValueError("free cells are not connected")
        self._dist = np.stack([bfs(self.walls, g) for g in range(SIZE * SIZE)])  # [goal, cell]
        # All (agent, goal) pairs over free cells, in gridnav's enumeration order, split 1500/256/rest.
        ar, ac, gr, gc = np.array(np.meshgrid(*[np.arange(SIZE)] * 4, indexing="ij")).reshape(4, -1)
        free = np.ones(SIZE * SIZE, bool)
        free[list(self.walls)] = False
        keep = free[ar * SIZE + ac] & free[gr * SIZE + gc]
        ar, ac, gr, gc = ar[keep], ac[keep], gr[keep], gc[keep]
        self._partition(self.encode(ar, ac, gr, gc), self.expert(ar, ac, gr, gc),
                        n_test=1500, n_val=256, split_seed=12345)

    def wall_free(self, ar, ac, gr, gc) -> np.ndarray:
        return GridNav.expert(self, ar, ac, gr, gc)

    def begins_shortest_path(self, action: int, ar, ac, gr, gc) -> np.ndarray:
        """Whether moving `action` (1 up, 2 down, 3 left, 4 right) from the agent starts a shortest path."""
        dr, dc = {1: (-1, 0), 2: (1, 0), 3: (0, -1), 4: (0, 1)}[action]
        nr, nc = ar + dr, ac + dc
        inside = (nr >= 0) & (nr < SIZE) & (nc >= 0) & (nc < SIZE)
        n = np.where(inside, nr * SIZE + nc, 0)
        g = gr * SIZE + gc
        return inside & (self._dist[g, n] == self._dist[g, ar * SIZE + ac] - 1)  # walls have inf distance

    def expert(self, ar, ac, gr, gc) -> np.ndarray:
        wf = self.wall_free(ar, ac, gr, gc)
        begins = {a: self.begins_shortest_path(a, ar, ac, gr, gc) for a in (1, 2, 3, 4)}
        # First of right (4), left (3), down (2), up (1) that begins a shortest path: assign the
        # lowest priority first so higher priorities overwrite it.
        fallback = np.zeros_like(wf)
        for a in (1, 2, 3, 4):
            fallback = np.where(begins[a], a, fallback)
        wf_ok = np.zeros(len(wf), bool)
        for a in (1, 2, 3, 4):
            wf_ok |= (wf == a) & begins[a]
        out = np.where(wf_ok, wf, fallback)
        return np.where((ar == gr) & (ac == gc), 0, out).astype(np.int64)

    def task_spec(self) -> str:
        return GRIDNAV_SPEC
