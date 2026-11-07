import numpy as np


def build_weights():
    W0 = np.zeros((2, 32)); b0 = np.zeros(32)
    W1 = np.zeros((32, 32)); b1 = np.zeros(32)
    W2 = np.zeros((32, 2)); b2 = np.zeros(2)

    K = 8                      # knots per coordinate
    h = 0.75 / K               # knot spacing on |x_i| in [0, 0.75]
    knots = [j * h for j in range(K)]
    # slopes increments so that sum_j c_j relu(a - t_j) interpolates a^2 at knots
    c = [h] + [2 * h] * (K - 1)

    lo, hi = 0.4 ** 2, 0.75 ** 2
    m = (lo + hi) / 2          # center of band in s = r^2
    w = (hi - lo) / 2          # half-width
    off = h * h / 4            # center the (always-positive) interpolation error

    for i in range(2):
        for si, sgn in enumerate((1.0, -1.0)):
            for j in range(K):
                u = i * 16 + si * 8 + j
                W0[i, u] = sgn
                b0[u] = -knots[j]
                W1[u, 0] = c[j]       # A = relu(s - m)
                W1[u, 1] = -c[j]      # B = relu(m - s)
    b1[0] = -off - m
    b1[1] = off + m

    # logit1 - logit0 = w - |s - m|, positive iff lo < s < hi
    scale = 100.0
    W2[0, 1] = -scale
    W2[1, 1] = -scale
    b2[1] = scale * w
    return {"W0": W0, "b0": b0, "W1": W1, "b1": b1, "W2": W2, "b2": b2}
