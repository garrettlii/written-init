"""Hand-written weights: wall-free greedy navigation rule + position features for fine-tuning.

Layer 1 (64): ReLU ramps of u1 = dc - dr, u2 = dc + dr, dc, dr, plus one-hot copies of
              agent row/col and goal row/col.
Layer 2 (64): exact 0/1 indicators of the rule region (right/left/down/up/stay), signs of
              dc/dr, and pass-through copies of the position one-hots.
Output:       K * (rule indicator) + small fallback-order preferences.
"""
import numpy as np

K = 3.0                      # confidence of the wall-free rule
EPS = {4: 1.0, 3: 0.8, 2: 0.6, 1: 0.4}   # fallback order right > left > down > up


def build_weights():
    W0 = np.zeros((162, 64)); b0 = np.zeros(64)
    W1 = np.zeros((64, 64)); b1 = np.zeros(64)
    W2 = np.zeros((64, 5)); b2 = np.zeros(5)

    # linear functions of the input: value = sum_agent wa[cell] + sum_goal wg[cell]
    def lin(f):
        w = np.zeros(162)
        for r in range(9):
            for c in range(9):
                w[r * 9 + c] = -f(r, c)       # agent contributes -coord
                w[81 + r * 9 + c] = f(r, c)   # goal contributes +coord
        return w

    u1 = lin(lambda r, c: c - r)   # dc - dr
    u2 = lin(lambda r, c: c + r)   # dc + dr
    dc = lin(lambda r, c: c)
    dr = lin(lambda r, c: r)

    # ramps: for integer v, relu(v+1)-relu(v) = [v>=0], relu(-v+1)-relu(-v) = [v<=0]
    def ramps(start, v):
        specs = [(v, 1.0), (v, 0.0), (-v, 1.0), (-v, 0.0)]
        for k, (w, b) in enumerate(specs):
            W0[:, start + k] = w; b0[start + k] = b
    ramps(0, u1)
    ramps(4, u2)
    # for dc, dr: relu(v)-relu(v-1) = [v>=1], relu(-v)-relu(-v-1) = [v<=-1]
    def ramps2(start, v):
        specs = [(v, 0.0), (v, -1.0), (-v, 0.0), (-v, -1.0)]
        for k, (w, b) in enumerate(specs):
            W0[:, start + k] = w; b0[start + k] = b
    ramps2(8, dc)
    ramps2(12, dr)

    # one-hot copies: agent row 16-24, agent col 25-33, goal row 34-42, goal col 43-51
    for r in range(9):
        for c in range(9):
            a = r * 9 + c
            W0[a, 16 + r] = 1.0
            W0[a, 25 + c] = 1.0
            W0[81 + a, 34 + r] = 1.0
            W0[81 + a, 43 + c] = 1.0

    # ---- layer 2 ----
    G1 = {0: 1.0, 1: -1.0}   # [u1>=0]
    L1 = {2: 1.0, 3: -1.0}   # [u1<=0]
    G2 = {4: 1.0, 5: -1.0}   # [u2>=0]
    L2 = {6: 1.0, 7: -1.0}   # [u2<=0]

    def add(unit, terms, bias):
        for sign, d in terms:
            for i, w in d.items():
                W1[i, unit] += sign * w
        b1[unit] = bias

    add(0, [(1, G1), (1, G2)], -1.0)                     # right_raw (incl. stay)
    add(1, [(1, L1), (1, L2)], -1.0)                     # left_raw (incl. stay)
    add(2, [(-1, G1), (-1, L2)], 1.0)                    # down: u1<0, u2>0
    add(3, [(-1, L1), (-1, G2)], 1.0)                    # up:   u1>0, u2<0
    add(4, [(1, G1), (1, L1), (1, G2), (1, L2)], -3.0)   # stay: u1=u2=0
    add(5, [(1, {8: 1.0, 9: -1.0})], 0.0)                # [dc>0]
    add(6, [(1, {10: 1.0, 11: -1.0})], 0.0)              # [dc<0]
    add(7, [(1, {12: 1.0, 13: -1.0})], 0.0)              # [dr>0]
    add(8, [(1, {14: 1.0, 15: -1.0})], 0.0)              # [dr<0]
    for k in range(36):                                  # position pass-through
        W1[16 + k, 9 + k] = 1.0

    # ---- output ----
    W2[4, 0] = K
    W2[3, 1] = K; W2[8, 1] = EPS[1]
    W2[2, 2] = K; W2[7, 2] = EPS[2]
    W2[1, 3] = K; W2[4, 3] = -K; W2[6, 3] = EPS[3]
    W2[0, 4] = K; W2[4, 4] = -K; W2[5, 4] = EPS[4]

    return {"W0": W0, "b0": b0, "W1": W1, "b1": b1, "W2": W2, "b2": b2}
