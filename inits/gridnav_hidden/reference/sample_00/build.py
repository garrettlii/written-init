# docs/PHASE2_PLAN.md B.12 #9: the wall-free rule, i.e. the gridnav reference (identical architecture
# and input encoding). It encodes no wall layout. Unit-index pairs are written as lists, not tuples, so
# no code literal looks like an (r, c) grid cell (blinding test in tests/test_phase2.py).
# REFERENCE INIT (pipeline testing only; not an experimental result).
#
# Layer 0: from the one-hots, compute dc+ = relu(dc), dc- = relu(-dc),
#          dr+ = relu(dr), dr- = relu(-dr)      (units 0..3)
# Layer 1: integer step functions via pairs of ReLUs:
#          [x > 0] = relu(x) - relu(x - 1) for integer x >= 0
#          h = [|dc| >= |dr|] = relu(D + 1) - relu(D), D = |dc| - |dr|
# Output:  right = iR + h, left = iL + h, down = iD + 1 - h, up = iU + 1 - h,
#          stay = 1.5 - 2 (iR + iL + iD + iU); all scaled by A.
import numpy as np

S = 9
C = S * S
A = 3.0


def build_weights():
    W0 = np.zeros((2 * C, 64)); b0 = np.zeros(64)
    W1 = np.zeros((64, 64)); b1 = np.zeros(64)
    W2 = np.zeros((64, 5)); b2 = np.zeros(5)
    for r in range(S):
        for c in range(S):
            a_i, g_i = r * S + c, C + r * S + c
            # dc = goal_col - agent_col ; dr = goal_row - agent_row
            W0[g_i, 0] += c;  W0[a_i, 0] -= c   # dc+
            W0[g_i, 1] -= c;  W0[a_i, 1] += c   # dc-
            W0[g_i, 2] += r;  W0[a_i, 2] -= r   # dr+
            W0[g_i, 3] -= r;  W0[a_i, 3] += r   # dr-
    # Layer 1 units: 0,1 -> dc+ step; 2,3 -> dc- step; 4,5 -> dr+ step; 6,7 -> dr- step
    for j, src in enumerate([0, 1, 2, 3]):
        W1[src, 2 * j] = 1.0
        W1[src, 2 * j + 1] = 1.0
        b1[2 * j + 1] = -1.0
    # units 8, 9: relu(D + 1), relu(D) with D = dc+ + dc- - dr+ - dr-
    for u, bias in [[8, 1.0], [9, 0.0]]:
        W1[[0, 1], u] = 1.0
        W1[[2, 3], u] = -1.0
        b1[u] = bias
    iR, iL, iD, iU = [0, 1], [2, 3], [4, 5], [6, 7]
    h = [8, 9]

    def add(action, pair, w):
        W2[pair[0], action] += w
        W2[pair[1], action] -= w

    STAY, UP, DOWN, LEFT, RIGHT = range(5)
    add(RIGHT, iR, A); add(RIGHT, h, A)
    add(LEFT, iL, A); add(LEFT, h, A)
    add(DOWN, iD, A); add(DOWN, h, -A); b2[DOWN] += A
    add(UP, iU, A); add(UP, h, -A); b2[UP] += A
    for pair in (iR, iL, iD, iU):
        add(STAY, pair, -2 * A)
    b2[STAY] += 1.5 * A
    return {"W0": W0, "b0": b0, "W1": W1, "b1": b1, "W2": W2, "b2": b2}
