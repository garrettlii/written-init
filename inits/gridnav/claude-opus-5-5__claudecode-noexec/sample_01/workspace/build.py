import numpy as np


def build_weights():
    W0 = np.zeros((162, 64)); b0 = np.zeros(64)
    W1 = np.zeros((64, 64)); b1 = np.zeros(64)
    W2 = np.zeros((64, 5)); b2 = np.zeros(5)

    # Layer 1: p=relu(dc), q=relu(-dc), s=relu(dr), t=relu(-dr)
    for r in range(9):
        for c in range(9):
            a = r * 9 + c       # agent index
            g = 81 + r * 9 + c  # goal index
            W0[g, 0] = c;  W0[a, 0] = -c   # dc
            W0[g, 1] = -c; W0[a, 1] = c    # -dc
            W0[g, 2] = r;  W0[a, 2] = -r   # dr
            W0[g, 3] = -r; W0[a, 3] = r    # -dr

    # Layer 2: identity pass-through (inputs are already >= 0)
    for i in range(4):
        W1[i, i] = 1.0

    # Output: logits linear in p, q, s, t  (|dc| = p+q, |dr| = s+t)
    p, q, s, t = 0, 1, 2, 3
    # stay: 1 - (|dc| + |dr|)
    W2[[p, q, s, t], 0] = -1.0; b2[0] = 1.0
    # up: -dr - |dc|
    W2[s, 1] = -1; W2[t, 1] = 1; W2[p, 1] = -1; W2[q, 1] = -1
    # down: dr - |dc|
    W2[s, 2] = 1; W2[t, 2] = -1; W2[p, 2] = -1; W2[q, 2] = -1
    # left: -dc - |dr| + 0.5  (0.5 breaks |dc|==|dr| ties toward horizontal)
    W2[p, 3] = -1; W2[q, 3] = 1; W2[s, 3] = -1; W2[t, 3] = -1; b2[3] = 0.5
    # right: dc - |dr| + 0.5
    W2[p, 4] = 1; W2[q, 4] = -1; W2[s, 4] = -1; W2[t, 4] = -1; b2[4] = 0.5

    scale = 10.0
    W2 *= scale; b2 *= scale

    return {"W0": W0, "b0": b0, "W1": W1, "b1": b1, "W2": W2, "b2": b2}
