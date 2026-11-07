import math
import numpy as np


def build_weights():
    K = 32          # layer-1 directions
    M = 32          # layer-2 radial hinges
    dt = 0.035      # hinge spacing in radius units
    H = 4.0         # logit-difference magnitude (inside = +H, outside = -H)

    # Layer 1: h1_k = relu(u_k . x), u_k evenly spaced unit vectors on the circle.
    # sum_k h1_k ~= r * K / pi  (ripple ~0.1%)
    theta = 2.0 * math.pi * np.arange(K) / K
    W0 = np.stack([np.cos(theta), np.sin(theta)], axis=0).astype(np.float64)  # (2, K)
    b0 = np.zeros(K)

    # Layer 2: h2_j = relu(r - t_j), with r = (pi/K) * sum_k h1_k.
    t = dt * np.arange(M)                     # 0 .. 1.085
    W1 = np.full((K, M), math.pi / K)
    b1 = -t

    # Output: f(r) = logit1 - logit0, a trapezoid bump built from 4 hinges.
    # Default ring: ramps centred at r_in ~ 0.385 and r_out ~ 0.77 (≈35% of square).
    i_a, i_b, i_c, i_d = 10, 12, 21, 23
    d = t[i_b] - t[i_a]
    slope = 2.0 * H / d
    coef = np.zeros(M)
    coef[i_a] += slope
    coef[i_b] -= slope
    coef[i_c] -= slope
    coef[i_d] += slope
    W2 = np.stack([-coef / 2.0, coef / 2.0], axis=1)   # (M, 2)
    b2 = np.array([H / 2.0, -H / 2.0])                 # f(0) = -H

    return {
        "W0": W0.astype(np.float32),
        "b0": b0.astype(np.float32),
        "W1": W1.astype(np.float32),
        "b1": b1.astype(np.float32),
        "W2": W2.astype(np.float32),
        "b2": b2.astype(np.float32),
    }


if __name__ == "__main__":
    w = build_weights()
    for k, v in w.items():
        print(k, v.shape)
