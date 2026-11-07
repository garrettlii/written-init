import numpy as np

# Six "parity heads".  Head h computes a soft selection sum s_h = sum_i g_i x_i
# (one layer-1 unit), and layer 2 turns s_h into a periodic trapezoid wave
# T(s) = +1 near even s, -1 near odd s (10 ReLU kinks).  Output = -alpha * sum_h T_h.
# If fine-tuning drives g -> 1 on the 4 relevant bits and -> 0 elsewhere,
# T(s) is exactly the parity.  The init g is chosen so that the gradient of
# E[Y*T] w.r.t. g is nonzero and points toward the relevant bits for every
# possible 4-subset (cos-of-sum factorises over bits -> 4th-order Fourier signal).

LAM = 4.0      # layer-0 weights are g/LAM, layer-1 weights carry LAM (g learns LAM x faster)
LAM2 = 0.5     # layer-2 activation scale (keeps W2 entries large vs Adam steps)
ALPHA = 0.3    # output amplitude per head
B = 1.0        # offset so h1 stays positive even if s goes slightly negative
G_IN = 0.36    # weight on the head's 8 focus bits
G_OUT = 0.14   # weight on the other 8 bits (8*0.36 + 8*0.14 = 4 -> wave phase centred at s=2)

BLOCKS = [list(range(0, 4)), list(range(4, 8)), list(range(8, 12)), list(range(12, 16))]
PAIRS = [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]

KINKS = [0.25 + 0.5 * m for m in range(10)]
SLOPES = [-4.0, 4.0, 4.0, -4.0, -4.0, 4.0, 4.0, -4.0, -4.0, 4.0]


def build_weights():
    W0 = np.zeros((16, 64))
    b0 = np.zeros(64)
    W1 = np.zeros((64, 64))
    b1 = np.zeros(64)
    W2 = np.zeros((64, 2))
    b2 = np.zeros(2)

    for h, (p, q) in enumerate(PAIRS):
        focus = set(BLOCKS[p] + BLOCKS[q])
        for i in range(16):
            W0[i, h] = (G_IN if i in focus else G_OUT) / LAM
        b0[h] = B / LAM                      # LAM*h1 = s + B
        for m, (k, a) in enumerate(zip(KINKS, SLOPES)):
            u = 10 * h + m
            W1[h, u] = LAM * LAM2            # h2_u = LAM2 * relu(s - k)
            b1[u] = -LAM2 * (B + k)
            W2[u, 0] = ALPHA * a / (2 * LAM2)
            W2[u, 1] = -ALPHA * a / (2 * LAM2)
    n_heads = len(PAIRS)
    b2[0] = ALPHA * n_heads / 2.0            # constant +1 of each trapezoid
    b2[1] = -ALPHA * n_heads / 2.0
    # logit1 - logit0 = -ALPHA * sum_h T(s_h)

    return {"W0": W0, "b0": b0, "W1": W1, "b1": b1, "W2": W2, "b2": b2}
