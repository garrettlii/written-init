"""Hand-written weights: exact wall-free shortest-path policy + fine-tunable hooks for walls."""
import numpy as np

N = 9
NC = N * N
SCALE = 5.0   # logit margin between the correct class and every other class (>= SCALE)
B = 10.0      # keeps the 5 class units of layer 2 always active (s_k >= -8)


def build_weights():
    W0 = np.zeros((2 * NC, 64))
    b0 = np.zeros(64)
    W1 = np.zeros((64, 64))
    b1 = np.zeros(64)
    W2 = np.zeros((64, 5))
    b2 = np.zeros(5)

    rows = np.array([i // N for i in range(NC)], dtype=float)
    cols = np.array([i % N for i in range(NC)], dtype=float)

    # ---- Layer 1: rule features (dc, dr are linear in the one-hot input) ----
    # dc = sum c*goal - sum c*agent ; dr likewise with rows.
    def set_lin(unit, coord, sign, bias):
        W0[:NC, unit] = -sign * coord   # agent
        W0[NC:, unit] = sign * coord    # goal
        b0[unit] = bias

    set_lin(0, cols, +1, 0.0)   # h0 = relu(dc)
    set_lin(1, cols, -1, 0.0)   # h1 = relu(-dc)
    set_lin(2, cols, +1, -1.0)  # h2 = relu(dc-1)
    set_lin(3, cols, -1, -1.0)  # h3 = relu(-dc-1)
    set_lin(4, rows, +1, 0.0)   # h4 = relu(dr)
    set_lin(5, rows, -1, 0.0)   # h5 = relu(-dr)
    set_lin(6, rows, +1, -1.0)  # h6 = relu(dr-1)
    set_lin(7, rows, -1, -1.0)  # h7 = relu(-dr-1)

    # ---- Layer 1: per-cell offset units, one per move (up,down,left,right) ----
    # Value is always 2 (agent one-hot + goal one-hot); each per-cell input weight
    # acts as a trainable "agent at / goal at this cell" offset on one move logit.
    for k in range(1, 5):
        u = 8 + (k - 1)
        W0[:, u] = 1.0
        W1[u, k] = 1.0
        b1[k] -= 2.0

    # ---- Layer 1: cut-crossing conjunction units (no initial effect) ----
    # relu([agent on side A] + [goal on side B] - 1): 1 iff the pair crosses a line.
    u = 12
    for kcut in range(1, N):
        for coord in (cols, rows):
            lo = (coord < kcut).astype(float)
            hi = 1.0 - lo
            for a_side, g_side in ((lo, hi), (hi, lo)):
                W0[:NC, u] = a_side
                W0[NC:, u] = g_side
                b0[u] = -1.0
                u += 1
    assert u == 44

    # ---- Layer 2: class scores (always-active, so effectively linear) ----
    # s_R = relu(dc) - |dr| + [dc>=1]   >=1 iff right, else <=0
    # s_L = relu(-dc) - |dr| + [dc<=-1]
    # s_D = relu(dr) - |dc|             >=1 iff down,  else <=0
    # s_U = relu(-dr) - |dc|
    # s_S = 1 - [dc>=1]-[dc<=-1]-[dr>=1]-[dr<=-1]
    # small eps encode the right>left>down>up tie order for fine-tuned fallbacks
    S = {
        0: ({0: -1, 2: 1, 1: -1, 3: 1, 4: -1, 6: 1, 5: -1, 7: 1}, 1.0),
        4: ({0: 2, 2: -1, 4: -1, 5: -1}, 0.03),
        3: ({1: 2, 3: -1, 4: -1, 5: -1}, 0.02),
        2: ({4: 1, 0: -1, 1: -1}, 0.01),
        1: ({5: 1, 0: -1, 1: -1}, 0.0),
    }
    for k, (terms, c) in S.items():
        for j, w in terms.items():
            W1[j, k] += w
        b1[k] += c + B

    # ---- Output ----
    for k in range(5):
        W2[k, k] = SCALE
        b2[k] = -SCALE * B

    return {"W0": W0, "b0": b0, "W1": W1, "b1": b1, "W2": W2, "b2": b2}
