"""Hand-written weights: wall-free greedy navigation policy + spare position features
for fine-tuning to learn instance-specific wall corrections."""
import numpy as np

N = 9
S = 5.0  # logit scale: correct wall-free class gets margin >= S


def build_weights():
    W0 = np.zeros((162, 64)); b0 = np.zeros(64)
    W1 = np.zeros((64, 64)); b1 = np.zeros(64)
    W2 = np.zeros((64, 5)); b2 = np.zeros(5)

    # ---- Layer 1 ----
    # 0: relu(dc)  1: relu(-dc)  2: relu(dr)  3: relu(-dr)
    # 4..12 agent-row one-hot, 13..21 agent-col, 22..30 goal-row, 31..39 goal-col
    for r in range(N):
        for c in range(N):
            a = r * N + c          # agent input index
            g = 81 + r * N + c     # goal input index
            # dc = gc - ac, dr = gr - ar
            W0[a, 0] = -c; W0[g, 0] = c
            W0[a, 1] = c;  W0[g, 1] = -c
            W0[a, 2] = -r; W0[g, 2] = r
            W0[a, 3] = r;  W0[g, 3] = -r
            W0[a, 4 + r] = 1.0
            W0[a, 13 + c] = 1.0
            W0[g, 22 + r] = 1.0
            W0[g, 31 + c] = 1.0

    # ---- Layer 2 ----
    # |dc| = h[0]+h[1], |dr| = h[2]+h[3]
    # 0 stay = relu(1 - |dc| - |dr|)                 (1 iff dc=dr=0)
    W1[0:4, 0] = -1.0; b1[0] = 1.0
    # 1 up   = relu(2(-dr - |dc|) - 1)   (>=1 iff -dr > |dc|)
    W1[[0, 1, 2, 3], 1] = [-2, -2, -2, 2]; b1[1] = -1.0
    # 2 down = relu(2(dr - |dc|) - 1)    (>=1 iff dr > |dc|)
    W1[[0, 1, 2, 3], 2] = [-2, -2, 2, -2]; b1[2] = -1.0
    # 3 left = relu(2(-dc - |dr|) + 1)   (>=1 iff -dc >= |dr|)
    W1[[0, 1, 2, 3], 3] = [-2, 2, -2, -2]; b1[3] = 1.0
    # 4 right= relu(2(dc - |dr|) + 1)    (>=1 iff dc >= |dr|)
    W1[[0, 1, 2, 3], 4] = [2, -2, -2, -2]; b1[4] = 1.0
    # 5..40: pass-through of the 36 position one-hots
    for k in range(36):
        W1[4 + k, 5 + k] = 1.0

    # ---- Output ----
    W2[0, 0] = S
    W2[1, 1] = S
    W2[2, 2] = S
    W2[3, 3] = S; W2[0, 3] = -S   # left/right both fire at dc=dr=0; cancel there
    W2[4, 4] = S; W2[0, 4] = -S
    # rows 5..40 left zero: fine-tuning can learn additive per-row/col corrections

    return {"W0": W0, "b0": b0, "W1": W1, "b1": b1, "W2": W2, "b2": b2}
