"""Hand-written weights for 4-bit parity of x[1], x[5], x[9], x[14]."""
import numpy as np

TAPS = [1, 5, 9, 14]


def build_weights():
    W0 = np.zeros((16, 64)); b0 = np.zeros(64)
    W1 = np.zeros((64, 64)); b1 = np.zeros(64)
    W2 = np.zeros((64, 2)); b2 = np.zeros(2)

    # Layer 1: unit k = relu(s - k), s = sum of tapped bits, k = 0..3
    for k in range(4):
        for i in TAPS:
            W0[i, k] = 1.0
        b0[k] = -float(k)

    # Layer 2: unit 0 = relu(s - 2relu(s-1) + 2relu(s-2) - 2relu(s-3)) = parity (0/1)
    W1[0, 0] = 1.0
    W1[1, 0] = -2.0
    W1[2, 0] = 2.0
    W1[3, 0] = -2.0

    # Output: logit1 = p, logit0 = 0.5
    W2[0, 1] = 1.0
    b2[0] = 0.5
    return {"W0": W0, "b0": b0, "W1": W1, "b1": b1, "W2": W2, "b2": b2}
