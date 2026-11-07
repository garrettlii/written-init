# REFERENCE INIT (pipeline testing only; not an experimental result).
# Written by hand to the same rules as LLM samples.
#
# Algorithm: s = number of relevant bits that are 1 (0..4). Parity is the
# piecewise-linear function through (k, k mod 2), which ReLUs express exactly:
#   p(s) = r(s) - 2 r(s-1) + 2 r(s-2) - 2 r(s-3) + 2 r(s-4),  r = relu
# Layer 0 computes r(s - k) for k = 0..4, layer 1 passes them through, and the
# output layer forms +/- A (p - 1/2).
import numpy as np

RELEVANT = [1, 5, 9, 14]
A = 4.0


def build_weights():
    W0 = np.zeros((16, 64)); b0 = np.zeros(64)
    W1 = np.zeros((64, 64)); b1 = np.zeros(64)
    W2 = np.zeros((64, 2)); b2 = np.zeros(2)
    for k in range(5):
        W0[RELEVANT, k] = 1.0
        b0[k] = -float(k)
        W1[k, k] = 1.0
    coef = np.array([1.0, -2.0, 2.0, -2.0, 2.0])
    W2[:5, 1] = A * coef
    W2[:5, 0] = -A * coef
    b2[1] = -A * 0.5
    b2[0] = A * 0.5
    return {"W0": W0, "b0": b0, "W1": W1, "b1": b1, "W2": W2, "b2": b2}
