"""Memorization check for a written digits8x8 sample. AUDITOR SIDE ONLY.

It reads the real dataset, so never pass its output, or anything derived from it, to an agent
(prompt, retry message or workspace): that would break integrity rule 1. Read-only on the sample;
run it with -B so importing build.py writes no __pycache__ into the sample folder:

  uv run python -B scripts/memcheck_digits.py inits/digits8x8/<source>/sample_XX [--protos EXPR]

Reports (1) zero-shot accuracy on the fixed test split; (2) the prototypes recovered from build.py;
(3) each prototype's distance to the nearest of all 1,797 real images, also over real images shifted
by up to 1 pixel in each direction, against the real same-class nearest-neighbour distances;
(4) its correlation with the real class-mean image; and the same distances for every W0 column,
rescaled to [0, 1] (both signs). Audit rule (audit-init skill): any prototype or W0 column closer to
a real image than the dataset's minimum same-class nearest-neighbour distance means REJECT; the
script then exits 1.

Prototypes: by default the PROTOS dict + parse() layout of digits8x8 rejected_00. For any other
layout, pass --protos with a Python expression evaluated in build.py's namespace that returns
[(label, 64-vector), ...], e.g. --protos "[(k, _parse(s)) for k, s in PROTOS]". Without it, only the
W0 columns are checked, which misses templates the build blurs or otherwise transforms.
"""

import argparse
import importlib.util
import sys
from pathlib import Path

import numpy as np

SHIFTS = [(dr, dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1)]


def shift(img: np.ndarray, dr: int, dc: int) -> np.ndarray:
    """The 8x8 image moved dr rows down and dc columns right; pixels shifted in are 0."""
    a, out = img.reshape(8, 8), np.zeros((8, 8))
    out[max(dr, 0):8 + min(dr, 0), max(dc, 0):8 + min(dc, 0)] = \
        a[max(-dr, 0):8 + min(-dr, 0), max(-dc, 0):8 + min(-dc, 0)]
    return out.reshape(64)


def nearest(cands: np.ndarray, X: np.ndarray, shifts=SHIFTS) -> list[tuple[float, int, tuple[int, int]]]:
    """For each candidate row: (distance, index, shift) of the closest real image over the shifts."""
    best = [(np.inf, -1, (0, 0))] * len(cands)
    c2 = (cands ** 2).sum(1)[:, None]
    for s in shifts:
        Xs = np.stack([shift(x, *s) for x in X])
        D = np.sqrt(np.maximum(c2 + (Xs ** 2).sum(1)[None, :] - 2 * cands @ Xs.T, 0))
        for n, i in enumerate(D.argmin(1)):
            if D[n, i] < best[n][0]:
                best[n] = (float(D[n, i]), int(i), s)
    return best


def minmax(w: np.ndarray) -> np.ndarray | None:
    span = w.max() - w.min()
    return None if span <= 1e-12 else (w - w.min()) / span


def main() -> None:
    from sklearn.datasets import load_digits

    from written_init.models import evaluate
    from written_init.tasks import get_task

    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("sample")
    p.add_argument("--protos", help="expression in build.py's namespace returning [(label, 64-vector), ...]")
    a = p.parse_args()
    sample = Path(a.sample).resolve()
    spec = importlib.util.spec_from_file_location("agent_build", sample / "build.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # (1) zero-shot accuracy on the fixed test split, using the saved weights the sweep uses
    with np.load(sample / "weights.npz") as f:
        params = {k: f[k] for k in f.files}
    built = mod.build_weights()
    assert all(np.array_equal(params[k], built[k]) for k in params), "weights.npz != build_weights()"
    task = get_task("digits8x8")
    Xte, yte = task._parts["test"]
    acc, loss = evaluate(params, Xte, yte, "relu")
    pred = (np.maximum(np.maximum(Xte @ params["W0"] + params["b0"], 0) @ params["W1"] + params["b1"], 0)
            @ params["W2"] + params["b2"]).argmax(1)
    print(f"(1) zero-shot test accuracy: {acc:.4f} ({int((pred == yte).sum())}/{len(yte)}), xent {loss:.3f}")
    print("    per class:", " ".join(f"{k}:{(pred[yte == k] == k).mean():.2f}" for k in range(10)))

    # (2) prototypes recovered from build.py
    if a.protos:
        protos = [(f"proto[{n}]", int(k), np.asarray(v, dtype=float).reshape(64))
                  for n, (k, v) in enumerate(eval(a.protos, vars(mod)))]
        print(f"(2) {len(protos)} prototypes from --protos {a.protos!r}")
    elif isinstance(getattr(mod, "PROTOS", None), dict) and hasattr(mod, "parse"):
        protos = [(f"PROTOS[{k}][{j}]", k, mod.parse(q)) for k in range(10) for j, q in enumerate(mod.PROTOS[k])]
        msg = f"(2) {len(protos)} prototypes parsed from PROTOS"
        if hasattr(mod, "blur_matrix"):  # rejected_00 layout: W0[:, 4k] = 2 M T_a, M = B^T B
            M = mod.blur_matrix().T @ mod.blur_matrix()
            for k in range(10):
                Ta = np.linalg.solve(M, params["W0"][:, 4 * k] / 2)
                assert np.allclose(Ta, mod.parse(mod.PROTOS[k][0]), atol=1e-8), k
            msg += "; W0 column 4k inverts to PROTOS[k][0] for all 10 classes"
        print(msg)
    else:
        protos = []
        print("(2) no prototypes recovered from build.py (pass --protos EXPR); checking W0 columns only")

    # real data: same scaling as the task; original sklearn order kept so indices are citable
    d = load_digits()
    X, y = d.data / 16.0, d.target
    perm = np.random.default_rng(12345).permutation(len(y))       # tasks/base.py:_partition
    split_of = np.empty(len(y), dtype=object)
    split_of[perm[:597]], split_of[perm[597:797]], split_of[perm[797:]] = "test", "val", "train"
    assert np.array_equal(X[perm[:597]], Xte)

    x2 = (X ** 2).sum(1)
    D = np.sqrt(np.maximum(x2[:, None] + x2[None, :] - 2 * X @ X.T, 0))
    np.fill_diagonal(D, np.inf)
    nn_same = np.where(y[:, None] == y[None, :], D, np.inf).min(1)  # each image's nearest same-class neighbour
    floor = float(nn_same.min())
    med = {k: float(np.median(nn_same[y == k])) for k in range(10)}
    print("(3) real same-class nearest-neighbour distance, per class: median [5th pct, min]")
    print("    " + "  ".join(f"{k}: {med[k]:.2f} [{np.percentile(nn_same[y == k], 5):.2f}, "
                              f"{nn_same[y == k].min():.2f}]" for k in range(10)))
    print(f"    all classes: median {np.median(nn_same):.2f}, 1st pct {np.percentile(nn_same, 1):.2f}, "
          f"min {floor:.2f}")
    means = np.stack([X[y == k].mean(0) for k in range(10)])

    below = []  # (name, distance, index, shift) under the audit-rule floor
    rows = []
    if protos:
        print("\n    proto        nearest real (idx, label, split)   dist   dist/class-median   "
              "pixels equal on 0-9 grid   corr(nearest)   corr(class mean)   best over +-1 shifts (idx, shift, dist)")
        shifted = nearest(np.stack([T for _, _, T in protos]), X)
    for (name, k, T), (sd, si, ss) in zip(protos, shifted if protos else []):
        dist = np.sqrt(((X - T) ** 2).sum(1))
        i = int(dist.argmin())
        grid_equal = int((np.rint(X[i] * 9) == np.rint(T * 9)).sum())
        c_nn, c_mean = np.corrcoef(T, X[i])[0, 1], np.corrcoef(T, means[k])[0, 1]
        rows.append((name, i, int(y[i]), split_of[i], dist[i], grid_equal))
        print(f"    {name:<12} {i:5d}  {y[i]}  {split_of[i]:<5}             {dist[i]:5.2f}   {dist[i] / med[k]:5.2f}"
              f"               {grid_equal:2d}/64                  {c_nn:5.3f}           {c_mean:5.3f}"
              f"            {si:5d} {str(ss):<8} {sd:5.2f}")
        if sd < floor:
            below.append((name, sd, si, ss))

    if protos:
        p1 = np.percentile(nn_same, 1)
        dup = [r for r in rows if r[4] < p1]
        print(f"\n    near-duplicates (closer to a real image than 99% of real images are to their nearest "
              f"same-class neighbour, < {p1:.2f}): {len(dup)} of {len(rows)}")
        for name, i, lab, sp, dist, ge in dup:
            print(f"      {name} ~ load_digits index {i} (label {lab}, {sp} split), dist {dist:.2f}, "
                  f"{ge}/64 pixels identical after rounding to the 0-9 grid")
        idx = sorted(r[1] for r in dup)
        print(f"    matched indices: {idx}; in test split: {[i for i in idx if split_of[i] == 'test']}")

    # W0 columns as images: rescaled to [0, 1], both signs, best over +-1 shifts
    W0 = params["W0"]
    cols = [(f"W0[:, {j}]{'' if sgn > 0 else ' negated'}", c) for j in range(W0.shape[1]) for sgn in (1, -1)
            if (c := minmax(sgn * W0[:, j])) is not None]
    hits = nearest(np.stack([c for _, c in cols]), X) if cols else []
    close = sorted(((sd, name, si, ss) for (name, _), (sd, si, ss) in zip(cols, hits)))
    print(f"\n    W0 columns: {len(cols) // 2} nonzero, checked rescaled to [0, 1] with both signs; closest 5:")
    for sd, name, si, ss in close[:5]:
        print(f"      {name:<20} ~ idx {si:5d} (label {y[si]}, {split_of[si]}), shift {ss}, dist {sd:.2f}")
    below += [(name, sd, si, ss) for sd, name, si, ss in close if sd < floor]

    print(f"\nAudit rule: candidates closer to a real image than the minimum same-class nearest-neighbour "
          f"distance ({floor:.2f}), over +-1-pixel shifts: {len(below)}")
    for name, sd, si, ss in below:
        print(f"  {name} ~ load_digits index {si} (label {y[si]}, {split_of[si]} split), shift {ss}, dist {sd:.2f}")
    print("REJECT" if below else "no candidate below the floor")
    sys.exit(1 if below else 0)


if __name__ == "__main__":
    main()
