import numpy as np


def build_weights():
    """Hand-written starting point for fine-tuning on an unknown 4-bit parity of 16 bits.

    Structure: 8 "blocks". Block (k, s) watches the 8 bits whose index has bit k == s
    (the 4 coordinate hyperplanes of F_2^4, both sides).
      layer 1: one unit per block,  u_b = 1 + 0.5 * (number of ones among its 8 bits)
               (a single shared "soft mask"; fine-tuning moves it toward 1 on S, 0 elsewhere)
      layer 2: 8 hinge units per block building a trapezoid wave g_b(v), v = u_b - 1,
               period 2, plateaus +1 at v = 0, 2, 4 and -1 at v = 1, 3.
               On the initial grid g_b = cos(pi*v); once the mask is 1 on S and 0 elsewhere,
               v = popcount(x_S) and g_b = (-1)^popcount = exact parity.
      output : logit1 - logit0 = -beta * sum_b g_b.
    """
    n_in, h1, h2, n_out = 16, 64, 64, 2
    W0 = np.zeros((n_in, h1))
    b0 = np.zeros(h1)
    W1 = np.zeros((h1, h2))
    b1 = np.zeros(h2)
    W2 = np.zeros((h2, n_out))
    b2 = np.zeros(n_out)

    mu = 0.5      # initial mask weight (8 bits * 0.5 = 4 = total weight of the final mask on S)
    B = 1.0       # offset keeping the mask unit active if some weights drift negative
    beta = 0.3    # output scale per block (keeps initial p near 0.5)

    knots = 0.25 + 0.5 * np.arange(8)                     # in v units, midway between grid points
    slope_changes = 4.0 * np.array([-1, 1, 1, -1, -1, 1, 1, -1], dtype=float)
    g_const = 1.0                                          # g_b(v) for v < first knot

    n_blocks = 0
    for k in range(4):
        for s in range(2):
            b = 2 * k + s
            for i in range(n_in):
                if ((i >> k) & 1) == s:
                    W0[i, b] = mu
            b0[b] = B
            for j in range(8):
                unit = 8 * b + j
                W1[b, unit] = 1.0
                b1[unit] = -(B + knots[j])
                W2[unit, 0] = beta * slope_changes[j] / 2.0
                W2[unit, 1] = -beta * slope_changes[j] / 2.0
            n_blocks += 1

    b2[0] = beta * g_const * n_blocks / 2.0
    b2[1] = -beta * g_const * n_blocks / 2.0

    return {"W0": W0, "b0": b0, "W1": W1, "b1": b1, "W2": W2, "b2": b2}
