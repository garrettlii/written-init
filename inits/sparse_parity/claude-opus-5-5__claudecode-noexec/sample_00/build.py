"""Hand-written weights for 4-bit parity of x[1], x[5], x[9], x[14]."""
import numpy as np

IDX = [1, 5, 9, 14]


def build_weights():
    W0 = np.zeros((16, 64)); b0 = np.zeros(64)
    W1 = np.zeros((64, 64)); b1 = np.zeros(64)
    W2 = np.zeros((64, 2)); b2 = np.zeros(2)

    # Layer 1: u_k = relu(s - k), k = 0..4, where s = sum of the relevant bits.
    for k in range(5):
        for i in IDX:
            W0[i, k] = 1.0
        b0[k] = -float(k)

    # Layer 2: f = s - 2u1 + 2u2 - 2u3 + 2u4 = parity(s) in {0, 1}.
    coeffs = [1.0, -2.0, 2.0, -2.0, 2.0]
    for k, c in enumerate(coeffs):
        W1[k, 0] = c
    b1[0] = 0.0

    # Output: logit1 - logit0 = 2f - 1.
    W2[0, 0] = -1.0; b2[0] = 0.5
    W2[0, 1] = 1.0;  b2[1] = -0.5

    return {"W0": W0, "b0": b0, "W1": W1, "b1": b1, "W2": W2, "b2": b2}
