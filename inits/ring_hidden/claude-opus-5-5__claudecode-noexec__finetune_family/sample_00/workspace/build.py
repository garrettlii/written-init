import math
import numpy as np

# Hyperparameters of the construction
N_DIR = 16            # directions in layer 1 (2 ReLUs each -> 32 units)
T0, DT = 0.07, 0.03   # layer-2 hinge thresholds t_j = T0 + DT*j, j=0..31 (0.07 .. 1.00)
G = 30.0              # gain of layer-2 hinge features
H = 4.0               # half-margin of the default logit difference
J_IN, J_OUT = 9, 22   # default ring: ramps between t_9..t_10 (r_in~0.355) and t_22..t_23 (r_out~0.745)


def build_weights():
    # Layer 1: |u_k . x| = relu(u_k.x) + relu(-u_k.x) for 16 directions over [0, pi).
    # Sum_k |u_k . x| = r * sum_k |cos(phi - theta_k)| ~= r * N_DIR * 2/pi (rel. error ~0.2%).
    W0 = np.zeros((2, 32))
    b0 = np.zeros(32)
    for k in range(N_DIR):
        th = math.pi * k / N_DIR
        u = np.array([math.cos(th), math.sin(th)])
        W0[:, 2 * k] = u
        W0[:, 2 * k + 1] = -u

    # Layer 2: h2_j = G * relu(r_hat - t_j), r_hat = (pi / (2*N_DIR)) * sum(h1)
    scale = math.pi / (2 * N_DIR)
    t = T0 + DT * np.arange(32)
    W1 = np.full((32, 32), G * scale)
    b1 = -G * t

    # Output: f(r) = logit1 - logit0, a trapezoid: -H outside, +H inside the default ring.
    c = 2 * H / (DT * G)
    a = np.zeros(32)
    a[J_IN] += c
    a[J_IN + 1] -= c
    a[J_OUT] -= c
    a[J_OUT + 1] += c
    W2 = np.zeros((32, 2))
    W2[:, 0] = -0.5 * a
    W2[:, 1] = 0.5 * a
    b2 = np.array([0.5 * H, -0.5 * H])

    return {"W0": W0, "b0": b0, "W1": W1, "b1": b1, "W2": W2, "b2": b2}
