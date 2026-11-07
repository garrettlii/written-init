import numpy as np


def build_weights():
    W0 = np.zeros((2, 32)); b0 = np.zeros(32)
    W1 = np.zeros((32, 32)); b1 = np.zeros(32)
    W2 = np.zeros((32, 2)); b2 = np.zeros(2)

    h = 1.0 / 8.0
    c = np.zeros(32)  # coefficient of each layer-1 unit in the x^2 interpolant
    idx = 0
    for d in range(2):          # coordinate
        for sign in (1.0, -1.0):
            for k in range(8):  # knots 0, 1/8, ..., 7/8
                W0[d, idx] = sign
                b0[idx] = -k * h
                c[idx] = h if k == 0 else 2 * h
                idx += 1
    # sum_j c_j h1_j = piecewise-linear interpolant of x0^2 + x1^2 (overestimates by [0, h^2/2])
    offset = h * h / 4.0  # center the error
    K = 1000.0
    thresholds = [0.4 ** 2, 0.75 ** 2]
    for i, t in enumerate(thresholds):
        for j, extra in enumerate((0.0, 1.0)):
            u = 2 * i + j
            W1[:, u] = K * c
            b1[u] = K * (-offset - t) - extra
    # step_low = u0 - u1, step_high = u2 - u3 ; in_ring = step_low - step_high
    W2[0, 1] = 1.0; W2[1, 1] = -1.0; W2[2, 1] = -1.0; W2[3, 1] = 1.0
    b2[0] = 0.5
    return {"W0": W0, "b0": b0, "W1": W1, "b1": b1, "W2": W2, "b2": b2}
