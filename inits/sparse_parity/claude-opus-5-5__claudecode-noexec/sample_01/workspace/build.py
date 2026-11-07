"""Hand-written weights for 4-bit parity of x[1], x[5], x[9], x[14]."""
import numpy as np

IDX = [1, 5, 9, 14]


def build_weights():
    W0 = np.zeros((16, 64)); b0 = np.zeros(64)
    W1 = np.zeros((64, 64)); b1 = np.zeros(64)
    W2 = np.zeros((64, 2)); b2 = np.zeros(2)

    # Layer 1: r_k = relu(s - k), k = 0..3, where s = sum of the 4 relevant bits.
    for k in range(4):
        for i in IDX:
            W0[i, k] = 1.0
        b0[k] = -float(k)

    # parity(s) = r0 - 2 r1 + 2 r2 - 2 r3 for integer s in [0, 4]
    coef = [1.0, -2.0, 2.0, -2.0]
    # Layer 2: unit 0 = relu(odd), unit 1 = relu(1 - odd)
    for k in range(4):
        W1[k, 0] = coef[k]
        W1[k, 1] = -coef[k]
    b1[0] = 0.0
    b1[1] = 1.0

    # Output: logit1 = 10*odd, logit0 = 10*(1-odd)
    W2[0, 1] = 10.0
    W2[1, 0] = 10.0

    return {"W0": W0, "b0": b0, "W1": W1, "b1": b1, "W2": W2, "b2": b2}
