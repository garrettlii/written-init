import numpy as np


def build_weights():
    W0 = np.zeros((162, 64)); b0 = np.zeros(64)
    W1 = np.zeros((64, 64)); b1 = np.zeros(64)
    W2 = np.zeros((64, 5)); b2 = np.zeros(5)

    # Layer 1: a=relu(dr), b=relu(-dr), c=relu(dc), d=relu(-dc)
    for r in range(9):
        for c in range(9):
            ia = r * 9 + c
            ig = 81 + r * 9 + c
            W0[ig, 0] = r;  W0[ia, 0] = -r
            W0[ig, 1] = -r; W0[ia, 1] = r
            W0[ig, 2] = c;  W0[ia, 2] = -c
            W0[ig, 3] = -c; W0[ia, 3] = c
    A, B, C, D = 0, 1, 2, 3

    # Layer 2: step-function pairs on integer-valued margins
    def unit(j, coeffs, bias):
        for k, v in coeffs.items():
            W1[k, j] = v
        b1[j] = bias

    unit(0, {C: 1, D: -1, A: -1, B: -1}, 1)   # R1: dc-|dr|+1
    unit(1, {C: 1, D: -1, A: -1, B: -1}, 0)   # R2: dc-|dr|
    unit(2, {D: 1, C: -1, A: -1, B: -1}, 1)   # L1: -dc-|dr|+1
    unit(3, {D: 1, C: -1, A: -1, B: -1}, 0)   # L2
    unit(4, {A: 1, B: -1, C: -1, D: -1}, 0)   # D1: dr-|dc|
    unit(5, {A: 1, B: -1, C: -1, D: -1}, -1)  # D2: dr-|dc|-1
    unit(6, {B: 1, A: -1, C: -1, D: -1}, 0)   # U1: -dr-|dc|
    unit(7, {B: 1, A: -1, C: -1, D: -1}, -1)  # U2
    unit(8, {A: -1, B: -1, C: -1, D: -1}, 1)  # S: 1-|dr|-|dc|

    # Output
    W2[0, 4] = 1; W2[1, 4] = -1   # right = [dc >= |dr|]
    W2[2, 3] = 1; W2[3, 3] = -1   # left  = [-dc >= |dr|]
    W2[4, 2] = 1; W2[5, 2] = -1   # down  = [dr > |dc|]
    W2[6, 1] = 1; W2[7, 1] = -1   # up    = [-dr > |dc|]
    W2[8, 0] = 3                  # stay  = 3*[dr=dc=0] (beats right/left ties at origin)

    return {"W0": W0, "b0": b0, "W1": W1, "b1": b1, "W2": W2, "b2": b2}
