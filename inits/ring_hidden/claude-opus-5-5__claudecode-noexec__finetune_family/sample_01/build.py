import math
import numpy as np

# Default ring guess (prior centre of the allowed instances)
R_IN = 0.40
R_OUT = 0.75
W = 0.05      # half-width of each linear transition (in radius units)
K = 60.0      # slope of the radial logit function; plateau logit gap = K*W = 3


def build_weights():
    N = 16  # directions over a half circle -> 32 first-layer units
    # ---- Layer 0: |u_k . x| split into two ReLUs (relu(z)+relu(-z) = |z|)
    W0 = np.zeros((2, 32))
    b0 = np.zeros(32)
    for k in range(N):
        th = k * math.pi / N
        c, s = math.cos(th), math.sin(th)
        W0[:, 2 * k] = [c, s]
        W0[:, 2 * k + 1] = [-c, -s]
    # sum_k |cos(theta - th_k)| ~= 2N/pi (ripple < 0.25%), so
    # r_hat = (pi / (2N)) * sum(h1) ~= ||x||.

    # ---- Layer 1: radial hinge basis h2_j = relu(r_hat - t_j)
    special = [R_IN - W, R_IN + W, R_OUT - W, R_OUT + W]
    grid = list(np.linspace(0.05, 1.0, 28))
    knots = np.array(special + grid)
    W1 = np.full((32, 32), math.pi / (2 * N))
    b1 = -knots

    # ---- Layer 2: trapezoid bump in r using the four special hinges
    # f(r) = -K*W + K[r-(ri-W)]+ - K[r-(ri+W)]+ - K[r-(ro-W)]+ + K[r-(ro+W)]+
    # f = 0 exactly at r = R_IN and r = R_OUT, +K*W inside, -K*W outside.
    a = np.zeros(32)
    a[0], a[1], a[2], a[3] = K, -K, -K, K
    W2 = np.zeros((32, 2))
    W2[:, 1] = a / 2.0
    W2[:, 0] = -a / 2.0
    b2 = np.array([K * W / 2.0, -K * W / 2.0])

    return {
        "W0": W0.astype(np.float64),
        "b0": b0.astype(np.float64),
        "W1": W1.astype(np.float64),
        "b1": b1.astype(np.float64),
        "W2": W2.astype(np.float64),
        "b2": b2.astype(np.float64),
    }


if __name__ == "__main__":
    w = build_weights()
    for n, v in w.items():
        print(n, v.shape)
