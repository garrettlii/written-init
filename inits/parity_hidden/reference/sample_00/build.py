# REFERENCE INIT (pipeline testing only; not an experimental result).
# docs/PHASE2_PLAN.md B.12 #9: equal weights on all 16 bits feeding the Phase 1 ladder, extended to
# 17 rungs so it computes the parity of all 16 bits. It encodes no hidden subset.
#
# s = number of bits that are 1 (0..16). Parity is the piecewise-linear function through
# (k, k mod 2), which ReLUs express exactly:
#   p(s) = r(s) - 2 r(s-1) + 2 r(s-2) - ... + 2 r(s-16),  r = relu
# Layer 0 computes r(s - k) for k = 0..16, layer 1 passes them through, and the output layer
# forms +/- A (p - 1/2).
import numpy as np

N_BITS = 16
A = 4.0


def build_weights():
    W0 = np.zeros((16, 64)); b0 = np.zeros(64)
    W1 = np.zeros((64, 64)); b1 = np.zeros(64)
    W2 = np.zeros((64, 2)); b2 = np.zeros(2)
    for k in range(N_BITS + 1):
        W0[:, k] = 1.0
        b0[k] = -float(k)
        W1[k, k] = 1.0
    coef = np.array([1.0] + [2.0 * (-1) ** k for k in range(1, N_BITS + 1)])
    W2[:N_BITS + 1, 1] = A * coef
    W2[:N_BITS + 1, 0] = -A * coef
    b2[1] = -A * 0.5
    b2[0] = A * 0.5
    return {"W0": W0, "b0": b0, "W1": W1, "b1": b1, "W2": W2, "b2": b2}
