"""Hand-written nearest-prototype digit classifier for 8x8 UCI digits.

Layer 0: each hidden unit j holds a hand-drawn (slightly blurred) digit
         prototype t_j and computes  s_j = x.t_j - 0.5*||t_j||^2  (+ offset C
         so ReLU never clips). argmax_j s_j == nearest prototype in L2.
Layer 1: per class, max over its (<=2) prototypes via max(a,b) = b + relu(a-b).
Layer 2: sums the per-class units into the logit.
"""
import numpy as np

# '#' = ink, '+' = half ink, '.' = background.  (my own stylised drawings)
PROTOS = [
    (0, """
..####..
.##..##.
.#....#.
.#....#.
.#....#.
.#....#.
.##..##.
..####..
"""),
    (1, """
...##...
..###...
...##...
...##...
...##...
...##...
...##...
...##...
"""),
    (1, """
...##...
..###...
...##...
...##...
...##...
...##...
..####..
.+####+.
"""),
    (2, """
..####..
.##..##.
.....##.
....##..
...##...
..##....
.##.....
.######.
"""),
    (3, """
.#####..
.....##.
.....##.
..####..
.....##.
.....##.
.....##.
.#####..
"""),
    (4, """
...#....
..##.##.
.##..##.
##...##.
#######.
.....##.
.....##.
.....##.
"""),
    (4, """
.##..##.
.##..##.
.##..##.
.######.
.....##.
.....##.
.....##.
.....##.
"""),
    (5, """
.######.
.##.....
.##.....
.#####..
.....##.
.....##.
.....##.
.#####..
"""),
    (6, """
....##..
...##...
..##....
.##.....
.#####..
.##..##.
.##..##.
..####..
"""),
    (7, """
.######.
.....##.
....##..
....##..
...##...
...##...
..##....
..##....
"""),
    (7, """
.######.
.....##.
....##..
..####..
...##...
...##...
..##....
..##....
"""),
    (8, """
..####..
.##..##.
.##..##.
..####..
..####..
.##..##.
.##..##.
..####..
"""),
    (9, """
..####..
.##..##.
.##..##.
..#####.
.....##.
.....##.
....##..
..###...
"""),
    (9, """
..####..
.##..##.
.##..##.
..#####.
.....##.
.....##.
.....##.
.....##.
"""),
]

OFFSET = 40.0  # keeps every layer-0 pre-activation positive


def _parse(s):
    rows = [r for r in s.strip().splitlines()]
    assert len(rows) == 8 and all(len(r) == 8 for r in rows)
    m = {'#': 1.0, '+': 0.5, '.': 0.0}
    return np.array([[m[ch] for ch in r] for r in rows], dtype=float)


def _soften(t):
    k = np.array([[1, 2, 1], [2, 4, 2], [1, 2, 1]], dtype=float) / 16.0
    p = np.pad(t, 1)
    b = np.zeros_like(t)
    for dr in range(3):
        for dc in range(3):
            b += k[dr, dc] * p[dr:dr + 8, dc:dc + 8]
    return np.clip(0.7 * t + 0.3 * b, 0.0, 1.0)


def build_weights():
    W0 = np.zeros((64, 64)); b0 = np.zeros(64)
    W1 = np.zeros((64, 32)); b1 = np.zeros(32)
    W2 = np.zeros((32, 10)); b2 = np.zeros(10)

    by_class = {k: [] for k in range(10)}
    for j, (cls, art) in enumerate(PROTOS):
        t = _soften(_parse(art)).reshape(64)
        W0[:, j] = t
        b0[j] = OFFSET - 0.5 * float(t @ t)
        by_class[cls].append(j)

    u = 0
    for cls in range(10):
        js = by_class[cls]
        if len(js) == 1:
            W1[js[0], u] = 1.0; W2[u, cls] = 1.0; u += 1
        else:
            a, b = js
            W1[b, u] = 1.0; W2[u, cls] = 1.0; u += 1          # b
            W1[a, u] = 1.0; W1[b, u] = -1.0; W2[u, cls] = 1.0; u += 1  # relu(a-b)
    assert u <= 32
    return {"W0": W0, "b0": b0, "W1": W1, "b1": b1, "W2": W2, "b2": b2}
