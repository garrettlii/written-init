import numpy as np


def build_weights():
    W0 = np.zeros((162, 64)); b0 = np.zeros(64)
    W1 = np.zeros((64, 64)); b1 = np.zeros(64)
    W2 = np.zeros((64, 5)); b2 = np.zeros(5)

    # Linear dc = gc - ac, dr = gr - ar from the one-hot inputs.
    dc = np.zeros(162); dr = np.zeros(162)
    for r in range(9):
        for c in range(9):
            i = r * 9 + c
            dc[i] -= c; dc[81 + i] += c
            dr[i] -= r; dr[81 + i] += r

    # Layer 1 units: 0 relu(dc), 1 relu(dc-1), 2 relu(-dc), 3 relu(-dc-1),
    #                4 relu(dr), 5 relu(-dr)
    specs = [(dc, 0.0), (dc, -1.0), (-dc, 0.0), (-dc, -1.0), (dr, 0.0), (-dr, 0.0)]
    for j, (w, b) in enumerate(specs):
        W0[:, j] = w
        b0[j] = b

    # Layer 2: identity pass-through (inputs are already nonnegative).
    for j in range(6):
        W1[j, j] = 1.0

    # Output scores:
    #   stay  = 0.25
    #   right = relu(dc) + 0.5*[dc>=1] = 1.5*relu(dc) - 0.5*relu(dc-1)
    #   left  = 1.5*relu(-dc) - 0.5*relu(-dc-1)
    #   down  = relu(dr), up = relu(-dr)
    b2[0] = 0.25
    W2[0, 4] = 1.5; W2[1, 4] = -0.5
    W2[2, 3] = 1.5; W2[3, 3] = -0.5
    W2[4, 2] = 1.0
    W2[5, 1] = 1.0

    return {"W0": W0, "b0": b0, "W1": W1, "b1": b1, "W2": W2, "b2": b2}
