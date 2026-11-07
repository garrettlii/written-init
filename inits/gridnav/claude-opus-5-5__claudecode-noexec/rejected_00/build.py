"""Hand-written weights for the 9x9 greedy-move expert. See NOTES.md."""
import numpy as np


def build_weights():
    W0 = np.zeros((162, 64)); b0 = np.zeros(64)
    W1 = np.zeros((64, 64)); b1 = np.zeros(64)
    W2 = np.zeros((64, 5)); b2 = np.zeros(5)

    # u = dc - dr, v = dc + dr as linear functions of the two one-hots
    r, c = np.divmod(np.arange(81), 9)
    u = np.concatenate([r - c, c - r]).astype(float)
    v = np.concatenate([-(r + c), r + c]).astype(float)

    # layer 1: relu(s), relu(s-1) for s in (u, -u, v, -v); pairs give exact integer steps
    for k, s in enumerate([u, -u, v, -v]):
        W0[:, 2 * k] = s
        W0[:, 2 * k + 1] = s; b0[2 * k + 1] = -1

    e = np.eye(64)
    Pu, Nu, Pv, Nv = (e[2 * k] - e[2 * k + 1] for k in range(4))  # [u>=1], [u<=-1], [v>=1], [v<=-1]

    # layer 2: one {0,1} indicator per class, in class order
    W1[:, 0] = -(Pu + Nu + Pv + Nv); b1[0] = 1   # stay:  u == 0 and v == 0
    W1[:, 1] = Pu + Nv;              b1[1] = -1  # up:    u >= 1 and v <= -1
    W1[:, 2] = Nu + Pv;              b1[2] = -1  # down:  u <= -1 and v >= 1
    W1[:, 3] = -(Pu + Pv);           b1[3] = 1   # left (or stay):  u <= 0 and v <= 0
    W1[:, 4] = -(Nu + Nv);           b1[4] = 1   # right (or stay): u >= 0 and v >= 0

    # stay gets weight 2 so it beats left/right, which also fire at u == v == 0
    W2[0, 0] = 2; W2[1, 1] = W2[2, 2] = W2[3, 3] = W2[4, 4] = 1

    return {"W0": W0, "b0": b0, "W1": W1, "b1": b1, "W2": W2, "b2": b2}


if __name__ == "__main__":
    # self-check only (not used to set weights): compare against the expert on all 81*81 inputs
    w = build_weights()
    relu = lambda z: np.maximum(z, 0)
    ok = 0
    for a in range(81):
        for g in range(81):
            x = np.zeros(162); x[a] = 1; x[81 + g] = 1
            dr, dc = g // 9 - a // 9, g % 9 - a % 9
            y = 0 if dr == dc == 0 else (4 if dc > 0 else 3) if abs(dc) >= abs(dr) else (2 if dr > 0 else 1)
            h = relu(relu(x @ w["W0"] + w["b0"]) @ w["W1"] + w["b1"])
            ok += int(np.argmax(h @ w["W2"] + w["b2"]) == y)
    print(f"{ok}/6561")
    assert ok == 6561
