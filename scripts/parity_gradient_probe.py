"""Follow-up F1c analytic probe and its extension (docs/PHASE2_PLAN.md Amendments, 2026-11-04), no
training.

For an init and a relevant subset S: the label-dependent first-layer gradient D(S) = dL/dW0 with the
true labels minus dL/dW0 with soft labels (0.5, 0.5), exact over all 2^16 inputs (L = mean
cross-entropy, whose gradient is linear in the targets). Reports (a) the share of ||D(S)||^2 on S's 4
rows of W0 (even spread 0.25), (b) ||D(S)|| / ||dL/dW0||, (c) the rank of S among all 1,820 four-bit
subsets by D(S)'s energy on their rows (1 = most; ties count against S), (d) ||D(S)||. ||D(S)|| at
rounding level reads "no label signal". Rows: the written samples, and as baselines random He init
(seeds 0-19) and each sample's norm_matched and shuffled_noise (seeds 0-5), on instances i0-i5. Plus,
per written sample, (c) with each of the 1,820 subsets as the hidden subset. Prints and saves
quantities only, never the instances' subsets (B.5 blinding).

  uv run python scripts/parity_gradient_probe.py [--source <source>] [--out results/parity_probe_f1_baselines]

results/parity_probe_f1/ came from the first version (commit 667756e): the written rows' (a)-(c) only.
"""

import argparse
import itertools
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from written_init import seeding
from written_init.experiment import SweepConfig
from written_init.init_arms import (add_noise, init_random, load_weights, norm_matched, shuffle_within_tensors,
                                    written_samples)
from written_init.models import loss_and_grads
from written_init.paths import CONFIGS, RESULTS, ROOT
from written_init.tasks import family_instances, get_task

SOURCE = "claude-opus-5-5__claudecode-noexec__finetune_family"
ALL_X = ((np.arange(2**16)[:, None] >> np.arange(16)) & 1).astype(np.float64)  # all 2^16 inputs
SUBSETS = np.array(list(itertools.combinations(range(16), 4)))  # all 1,820 four-bit subsets
ZERO = 1e-9  # ||D|| at most this fraction of ||dL/dW0|| is rounding error, and the tie tolerance
N_RANDOM, N_DERIVED = 20, 6  # baseline seeds: random He init; norm_matched / shuffled_noise per sample


def _w0_grad(params, y, activation) -> np.ndarray:
    return loss_and_grads(params, ALL_X, y, activation)[1]["W0"]


def _soft_gradient(params, activation) -> np.ndarray:
    """The gradient is affine in the targets, so soft labels (0.5, 0.5) give the mean of the all-0 and
    all-1 label gradients."""
    zeros = np.zeros(len(ALL_X), np.int64)
    return (_w0_grad(params, zeros, activation) + _w0_grad(params, zeros + 1, activation)) / 2


def _stats(D, G, relevant) -> dict:
    norm_d = float(np.linalg.norm(D))
    ratio = norm_d / float(np.linalg.norm(G))
    if not ratio > ZERO:
        return {"label_signal": False, "share": None, "ratio": ratio, "rank": None, "norm_D": norm_d}
    per_bit = (D**2).sum(axis=1)  # W0 row j holds input bit j's weights
    e_s = per_bit[list(relevant)].sum()
    rank = int((per_bit[SUBSETS].sum(axis=1) >= e_s * (1 - ZERO)).sum())  # S counts last among ties
    return {"label_signal": True, "share": float(e_s / per_bit.sum()), "ratio": ratio, "rank": rank,
            "norm_D": norm_d}


def probe(params, task) -> dict:
    G = _w0_grad(params, task.label(ALL_X), task.activation)
    return _stats(G - _soft_gradient(params, task.activation), G, task.relevant)


def ranks_over_all_subsets(params, activation="relu") -> list[int | None]:
    """(c) with each of the 1,820 subsets as the hidden subset, in SUBSETS order; None = no label signal."""
    soft = _soft_gradient(params, activation)
    out = []
    for s in SUBSETS:
        G = _w0_grad(params, (ALL_X[:, s].sum(axis=1) % 2).astype(np.int64), activation)
        out.append(_stats(G - soft, G, s)["rank"])
    return out


def baseline_inits(task, written: dict, cfg: SweepConfig) -> list[tuple[str, str, int, dict]]:
    """(init, sample, seed, params), built with the sweep's streams and arm names (experiment.build_init)."""
    arms = {a.kind: a for a in cfg.arms}
    nm, sn = arms["norm_matched"], arms["shuffled_noise"]
    out = [("random", "-", s, init_random(task, seeding.rng(s, "init"))) for s in range(N_RANDOM)]
    for sid, params in written.items():
        for s in range(N_DERIVED):
            out.append(("norm_matched", sid, s, norm_matched(params, seeding.rng(s, "norm", nm.name))))
            shuffled = shuffle_within_tensors(params, seeding.rng(s, "shuffle", sn.name))
            out.append(("shuffled_noise", sid, s, add_noise(task, shuffled, sn.alpha, seeding.rng(s, "noise", sn.name))))
    return out


def _span(v, fmt) -> str:
    return "-" if not len(v) else f"{fmt.format(np.mean(v))} ({fmt.format(np.min(v))}-{fmt.format(np.max(v))})"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--source", default=SOURCE)
    p.add_argument("--out", default=str(RESULTS / "parity_probe_f1_baselines"))
    a = p.parse_args()
    out = Path(a.out)
    if out.exists():
        raise SystemExit(f"{out} exists; results folders are never overwritten")
    cfg = SweepConfig.load(CONFIGS / "phase2_parity_f1.yaml")  # arm names and alpha for the baselines
    tasks = [get_task(t) for t in family_instances("parity_hidden")]
    files = written_samples("parity_hidden", a.source, require_audited=True)
    if not files:
        raise SystemExit(f"no audited samples in inits/parity_hidden/{a.source}")
    git = lambda *c: subprocess.run(["git", *c], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    provenance = {"started": datetime.now(timezone.utc).isoformat(), "git_commit": git("rev-parse", "HEAD"),
                  "git_dirty": bool(git("status", "--porcelain")), "source": a.source}

    rows = []
    for t in tasks:
        written = {f.parent.name: load_weights(t, f) for f in files}
        inits = [("written", sid, None, w) for sid, w in written.items()] + baseline_inits(t, written, cfg)
        rows += [{"init": k, "sample": sid, "seed": s, "instance": t.name, **probe(w, t)} for k, sid, s, w in inits]
    df = pd.DataFrame(rows)
    ranks = {f.parent.name: ranks_over_all_subsets(load_weights(tasks[0], f)) for f in files}

    names = [t.name for t in tasks]
    lines = [f"# Parity gradient probe with baselines (F1c extension): {a.source}", "",
             "D(S) = dL/dW0 with the true labels minus with soft labels (0.5, 0.5), exact over all 2^16 inputs "
             "at initialization (docs/PHASE2_PLAN.md Amendments, F1c and its extension). (a) share of "
             "||D(S)||^2 on S's 4 rows of W0 (even spread 0.250); (b) ||D(S)|| / ||dL/dW0||; (c) rank of S "
             "among the 1,820 four-bit subsets by D(S)'s energy on their rows (1 = most; ties count against "
             "S); (d) ||D(S)||.", "", "## Written samples", ""]
    w = df[df.init == "written"]
    for col, title, fmt in [("share", "(a) share", "{:.3f}"), ("ratio", "(b) ||D(S)|| / ||dL/dW0||", "{:.3g}"),
                            ("rank", "(c) rank of 1,820", "{:.0f}"), ("norm_D", "(d) ||D(S)||", "{:.3g}")]:
        lines += [f"**{title}**", "", "| sample | " + " | ".join(names) + " |", "|---" * (1 + len(names)) + "|"]
        for sid, g in w.groupby("sample"):
            cells = [fmt.format(getattr(r, col)) if r.label_signal or col == "norm_D" else "no label signal"
                     for r in g.itertuples()]
            lines.append(f"| {sid} | " + " | ".join(cells) + " |")
        lines.append("")
    lines += ["## Baselines", "",
              f"Random He init: seeds 0-{N_RANDOM - 1}. norm_matched and shuffled_noise: seeds 0-{N_DERIVED - 1} of "
              "each written sample. (a)-(c) over the inits with label signal, as mean (min-max) or median "
              "(min-max); (d) over all inits.", "",
              "| init | sample | instance | inits | no label signal | (a) share | (b) ratio | (c) rank, median (min-max) | (d) ||D(S)|| |",
              "|---|---|---|---|---|---|---|---|---|"]
    for (k, sid, inst), g in df[df.init != "written"].groupby(["init", "sample", "instance"], sort=False):
        sig = g[g.label_signal]
        rank = (f"{np.median(sig['rank']):.0f} ({sig['rank'].min():.0f}-{sig['rank'].max():.0f})" if len(sig) else "-")
        lines.append(f"| {k} | {sid} | {inst} | {len(g)} | {int((~g.label_signal).sum())} | "
                     f"{_span(sig.share, '{:.3f}')} | {_span(sig.ratio, '{:.3g}')} | {rank} | {_span(g.norm_D, '{:.3g}')} |")
    lines += ["", "## (c) with every subset as the hidden subset (written samples)", "",
              "Each of the 1,820 four-bit subsets in turn is the hidden subset. A rank carrying no information "
              "about the subset would be spread over 1-1,820 (median about 910).", "",
              "| sample | subsets with label signal | rank 1 | rank <= 18 (top 1%) | rank <= 91 (top 5%) | "
              "rank percentiles 5 / 25 / 50 / 75 / 95 |", "|---|---|---|---|---|---|"]
    hist = []
    for sid, r in ranks.items():
        r_sig = np.array([v for v in r if v is not None])
        pct = " / ".join(f"{v:.0f}" for v in np.percentile(r_sig, [5, 25, 50, 75, 95])) if len(r_sig) else "-"
        lines.append(f"| {sid} | {len(r_sig)} | {(r_sig == 1).sum()} | {(r_sig <= 18).sum()} | {(r_sig <= 91).sum()} | {pct} |")
        hist += [{"sample": sid, "rank": v, "n_subsets": n}
                 for v, n in pd.Series(["none" if v is None else v for v in r]).value_counts().items()]
    out.mkdir(parents=True)
    (out / "provenance.json").write_text(json.dumps(provenance, indent=1))
    df.to_csv(out / "probe.csv", index=False)
    pd.DataFrame(hist).to_csv(out / "all_subset_ranks.csv", index=False)  # counts per rank: no subset identities
    (out / "report.md").write_text("\n".join(lines))
    print("\n".join(lines) + f"\nwrote {out}/report.md, probe.csv, all_subset_ranks.csv, provenance.json")


if __name__ == "__main__":
    main()
