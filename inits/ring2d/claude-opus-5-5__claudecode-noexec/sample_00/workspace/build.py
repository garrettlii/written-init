import numpy as np


def build_weights():
    h = 1.0 / 8.0          # knot spacing for piecewise-linear x^2
    W0 = np.zeros((2, 32)); b0 = np.zeros(32)
    coef = np.zeros(32)    # weight of each h1 unit in s_hat ~= x0^2 + x1^2
    idx = 0
    for d in range(2):
        for sg in (1.0, -1.0):
            for j in range(8):
                W0[d, idx] = sg
                b0[idx] = -j * h
                coef[idx] = h if j == 0 else 2 * h
                idx += 1

    # Interpolation overestimates x^2 by h^2/6 on average per coordinate.
    delta = 2 * h * h / 6.0
    a = 0.4 ** 2 + delta
    b = 0.75 ** 2 + delta
    e = 0.001
    offs = [-(a - e / 2), -(a + e / 2), -(b - e / 2), -(b + e / 2)]
    sgn = [1.0, -1.0, -1.0, 1.0]

    W1 = np.zeros((32, 32)); b1 = np.zeros(32)
    W2 = np.zeros((32, 2)); b2 = np.zeros(2)
    for k in range(4):
        W1[:, k] = coef
        b1[k] = offs[k]
        W2[k, 1] = sgn[k] / e
    b2[0] = 0.5
    return {"W0": W0, "b0": b0, "W1": W1, "b1": b1, "W2": W2, "b2": b2}
