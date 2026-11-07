# REFERENCE INIT (pipeline testing only; not an experimental result).
# docs/PHASE2_PLAN.md B.12 #9: r^2 with thresholds at the midpoint of each radius's feasible range
# under all the spec constraints (0.10 <= r_in < r_out <= 0.95, gap >= 0.15, inside fraction
# 0.20-0.50): r_in in [0.10, 0.80] -> 0.45; r_out in [sqrt(0.01 + 0.8/pi), 0.95] -> ~0.732.
# Construction as in the ring2d reference:
# Layer 0: for each coordinate, 8 knots t_j = j/8 and two hinge units each,
#          relu(x - t_j) + relu(-x - t_j) = relu(|x| - t_j). A weighted sum of
#          these interpolates x^2 on the knots (max error 1/256).
# Layer 1: u0 = R2 (the approximate squared radius), u1 = relu(2 R2 - (r1^2 + r2^2))
# Output:  margin = min(R2 - r1^2, r2^2 - R2) = u0 - r1^2 - u1 > 0 inside the ring.
import math

import numpy as np

R_IN = (0.10 + 0.80) / 2
R_OUT = (math.sqrt(0.10**2 + 0.8 / math.pi) + 0.95) / 2
R1SQ, R2SQ = R_IN**2, R_OUT**2
A = 20.0
H = 1.0 / 8


def build_weights():
    W0 = np.zeros((2, 32)); b0 = np.zeros(32)
    W1 = np.zeros((32, 32)); b1 = np.zeros(32)
    W2 = np.zeros((32, 2)); b2 = np.zeros(2)
    coef = np.array([H] + [2 * H] * 7)  # slope changes of the x^2 interpolant
    unit = 0
    for d in range(2):
        for j in range(8):
            t = j * H
            for sign in (1.0, -1.0):
                W0[d, unit] = sign
                b0[unit] = -t
                W1[unit, 0] = coef[j]           # u0 = R2
                W1[unit, 1] = 2 * coef[j]       # u1 pre-activation: 2 R2 ...
                unit += 1
    b1[1] = -(R1SQ + R2SQ)                      # ... - (r1^2 + r2^2)
    W2[0, 1] = A; W2[1, 1] = -A; b2[1] = -A * R1SQ
    return {"W0": W0, "b0": b0, "W1": W1, "b1": b1, "W2": W2, "b2": b2}
