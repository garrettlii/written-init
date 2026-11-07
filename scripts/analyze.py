"""Summarize a sweep: accuracy curves, data multipliers, plots, and a report.

  uv run python scripts/analyze.py results/smoke

Writes into the run folder: summary.csv, multipliers.csv, comparisons.csv, per_sample.csv, report.md,
figures/<task>.png, and for Phase 2 families (docs/PHASE2_PLAN.md B.8-B.9) family_primary.csv,
samples_to_target.csv and family_controls.csv.
"""

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from written_init.metrics import (bootstrap_multiplier, mean_ci, resolve, samples_to_target,  # noqa: E402
                                  stratified_mean_ci, target_ratio)
from written_init.tasks import get_task  # noqa: E402

CEILING = 0.995  # arm and random both at least this accurate at a budget: no multiplier to measure
# Phase 2 (docs/PHASE2_PLAN.md): samples-to-target levels, H9 parity band, pooled controls (B.8
# secondary 4) and the H10 budgets. Primary budgets are --primary-budgets (B.8: 16 64; F1a: 256).
TARGETS = (0.95, 0.99)
H9_BAND = (0.46, 0.54)
POOLED_PAIRS = [("written_noise", "shuffled_noise", "structure"), ("written", "norm_matched", "scale")]
H10_BUDGETS = (16, 64, 256)
F1C_BUDGET, F1C_TARGET = 128, 0.95  # follow-up F1c: cells reaching the target at this one budget

p = argparse.ArgumentParser()
p.add_argument("run_dir")
p.add_argument("--random-arm", default="random")
p.add_argument("--margin", type=float, default=0.02,
               help="accuracy margin for the chance and flat-curve rules (see metrics.resolve)")
p.add_argument("--primary-budgets", type=int, nargs="+", default=[16, 64],
               help="budgets of the Phase 2 primary table (B.8: 16 64; follow-up F1a: 256)")
a = p.parse_args()
run = Path(a.run_dir)
rows = [json.loads(l) for l in (run / "runs.jsonl").read_text().splitlines() if l.strip()]
df = pd.DataFrame(rows)

# ---- accuracy summary -------------------------------------------------------
summ = []
for (task, arm, budget), g in df.groupby(["task", "arm", "budget"]):
    m, lo, hi = mean_ci(g["test_acc"].to_numpy())
    summ.append({"task": task, "arm": arm, "budget": budget, "n_seeds": len(g),
                 "mean_test_acc": m, "ci_lo": lo, "ci_hi": hi,
                 "mean_best_step": g["best_step"].mean(),
                 "frac_selected_step0": float((g["best_step"] == 0).mean())})
summary = pd.DataFrame(summ).sort_values(["task", "arm", "budget"])
summary.to_csv(run / "summary.csv", index=False)

# ---- data multipliers ---------------------------------------------------------
def chance_for(task: str, gt: pd.DataFrame) -> float:
    """Accuracy of a constant majority-class predictor on the test set."""
    if "test_majority_acc" in gt and gt["test_majority_acc"].notna().any():
        return float(gt["test_majority_acc"].dropna().iloc[0])
    # Runs from before v0.3 didn't record it: recompute from the fixed test split.
    import yaml
    from written_init.experiment import _fixed_split
    cfg = yaml.safe_load((run / "config.yaml").read_text()) if (run / "config.yaml").exists() else {}
    _, y = _fixed_split(get_task(task), "test", cfg.get("test_size", 2000))
    return float(np.bincount(y).max() / len(y))


mult = []
for task, gt in df.groupby("task"):
    r = gt[(gt["arm"] == a.random_arm) & (gt["budget"] > 0)]
    if r.empty:
        print(f"[warn] {task}: no random-arm runs with budget > 0; skipping multipliers")
        continue
    chance = chance_for(task, gt)
    rand_by_b = {int(b): g["test_acc"].to_numpy() for b, g in r.groupby("budget")}
    rb = np.array(sorted(rand_by_b))
    rstats = [mean_ci(rand_by_b[b]) for b in rb]
    ra = np.array([m for m, _, _ in rstats])
    rh = np.array([(hi - lo) / 2 for _, lo, hi in rstats])
    for (arm, budget), g in gt[gt["arm"] != a.random_arm].groupby(["arm", "budget"]):
        accs = g["test_acc"].to_numpy()
        m, lo_acc, hi_acc = mean_ci(accs)
        n = int(budget)
        if n in rand_by_b and min(m, rand_by_b[n].mean()) >= CEILING:
            res = {"status": "ceiling", "n_eq": None, "lo": None, "hi": None}
        else:
            res = resolve(rb, ra, rh, m, (hi_acc - lo_acc) / 2, chance, a.margin)
        ci_lo = ci_hi = np.nan
        if res["status"] == "point":
            ci_lo, ci_hi = bootstrap_multiplier(rand_by_b, accs, n)
        per = (lambda x: (x / n) if (x is not None and n > 0) else x)
        mult.append({
            "task": task, "arm": arm, "budget": n, "n_seeds": len(accs), "mean_test_acc": m,
            "chance_acc": chance, "status": res["status"],
            "n_eq_point": res["n_eq"], "n_eq_lo": res["lo"], "n_eq_hi": res["hi"],
            "mult_point": per(res["n_eq"]), "mult_lo": per(res["lo"]), "mult_hi": per(res["hi"]),
            "ci_lo": ci_lo, "ci_hi": ci_hi, "ci_of": "multiplier" if n > 0 else "n_eq",
        })
mult_df = pd.DataFrame(mult)
mult_df.to_csv(run / "multipliers.csv", index=False)

# ---- control comparisons (paired by seed) -------------------------------------
def paired_diff(task: str, arm_a: str, arm_b: str, budget: int) -> np.ndarray:
    """Test-accuracy differences A - B at one budget, paired by seed (same training data per seed)."""
    sel = lambda arm: df[(df.task == task) & (df.arm == arm) & (df.budget == budget)].set_index("seed")["test_acc"]
    a_, b_ = sel(arm_a), sel(arm_b)
    return np.array([a_[s] - b_[s] for s in sorted(set(a_.index) & set(b_.index))])



# Revised H3: structure = written_noise vs shuffled_noise; scale = written vs norm_matched.
CONTROL_PAIRS = [("written_noise", "shuffled_noise", "structure"), ("written", "norm_matched", "scale"),
                 ("written", "shuffled", "structure (secondary)")]
comp = []
for (task, source), gs in df[df["source"].notna()].groupby(["task", "source"]):
    for kind_a, kind_b, what in CONTROL_PAIRS:
        A, B = gs[gs["kind"] == kind_a], gs[gs["kind"] == kind_b]
        if A.empty or B.empty:
            continue
        for budget in sorted(set(A["budget"]) & set(B["budget"])):
            d = paired_diff(task, A["arm"].iloc[0], B["arm"].iloc[0], budget)
            if not len(d):
                continue
            m, lo, hi = mean_ci(d)
            comp.append({"task": task, "source": source, "test": what, "arm_a": A["arm"].iloc[0],
                         "arm_b": B["arm"].iloc[0], "budget": int(budget), "n_seeds": len(d),
                         "mean_diff": m, "ci_lo": lo, "ci_hi": hi})
comp_df = pd.DataFrame(comp)
comp_df.to_csv(run / "comparisons.csv", index=False)

# ---- per-sample accuracy of written arms (samples are assigned to seeds round-robin) ----
per_sample = (df[df["kind"] == "written"].groupby(["task", "arm", "sample_id", "budget"])
              .agg(n_seeds=("seed", "size"), seeds=("seed", lambda s: " ".join(map(str, sorted(s)))),
                   mean_test_acc=("test_acc", "mean"), mean_test_loss=("test_loss", "mean"))
              .reset_index())
per_sample.to_csv(run / "per_sample.csv", index=False)

# ---- Phase 2 families (docs/PHASE2_PLAN.md B.8, B.9) ---------------------------
family_of = {t: get_task(t).family for t in df["task"].unique()}
fam_tasks = {f: sorted(t for t, g in family_of.items() if g == f)
             for f in sorted({f for t, f in family_of.items() if f != t})}
written_arms = lambda tasks: sorted(df[df.task.isin(tasks) & (df.kind == "written")].arm.unique())


def h9_canary(task: str) -> str:
    """Leak canary for one parity_hidden instance: written zero-shot accuracy must be 0.5 +- 0.04.
    Flags OUTSIDE if the arm mean or any single sample is outside the band (B.9)."""
    z = df[(df.task == task) & (df.kind == "written") & (df.budget == 0)]
    if z.empty:
        return f"**H9 canary ({task}):** no written arm at budget 0."
    inband = lambda v: H9_BAND[0] <= v <= H9_BAND[1]
    parts, bad = [], False
    for arm, g in z.groupby("arm"):
        vals = [(f"{arm} mean", g.test_acc.mean())] + [(sid, s.test_acc.mean()) for sid, s in g.groupby("sample_id")]
        bad |= not all(inband(v) for _, v in vals)
        parts.append(", ".join(f"{n} {v:.3f}{'' if inband(v) else ' (OUTSIDE)'}" for n, v in vals))
    verdict = ("**OUTSIDE 0.5 ± 0.04: possible leak. Investigate before reading any other Phase 2 result.**"
               if bad else "within 0.5 ± 0.04 (mean and every sample).")
    return f"**H9 canary ({task}):** written zero-shot {'; '.join(parts)}. {verdict}"


prim, stt, pooled = [], [], []
for fam, tasks in fam_tasks.items():
    for t in tasks:
        for arm in written_arms([t]):
            for b in a.primary_budgets:
                d = paired_diff(t, arm, a.random_arm, b)
                if len(d):
                    m, lo, hi = mean_ci(d)
                    prim.append({"family": fam, "task": t, "arm": arm, "budget": b, "n_seeds": len(d),
                                 "mean_diff": m, "ci_lo": lo, "ci_hi": hi})
        curves = {arm: g.sort_values("budget") for arm, g in summary[summary.task == t].groupby("arm")}
        for target in TARGETS:
            res = {arm: samples_to_target(g.budget.to_numpy(), g.mean_test_acc.to_numpy(), target)
                   for arm, g in curves.items()}
            for arm, (n, c) in res.items():
                ratio, kind = (target_ratio(res[a.random_arm], (n, c))
                               if arm != a.random_arm and a.random_arm in res else (None, ""))
                stt.append({"family": fam, "task": t, "arm": arm, "target": target, "n": n, "censor": c,
                            "ratio_random_over_arm": ratio, "ratio_kind": kind})
    for source, gs in df[df.task.isin(tasks) & df.source.notna()].groupby("source"):
        for kind_a, kind_b, what in POOLED_PAIRS:
            A, B = gs[gs.kind == kind_a], gs[gs.kind == kind_b]
            if A.empty or B.empty:
                continue
            for b in sorted(set(A.budget) & set(B.budget)):
                groups = [d for t in tasks if len(d := paired_diff(t, A.arm.iloc[0], B.arm.iloc[0], b))]
                if len(groups) < len(tasks):
                    continue  # pool-capped budgets differ per instance (A.4); pool only shared budgets
                m, lo, hi = stratified_mean_ci(groups)
                pooled.append({"family": fam, "source": source, "test": what, "arm_a": A.arm.iloc[0],
                               "arm_b": B.arm.iloc[0], "budget": int(b), "n_instances": len(groups),
                               "n_pairs": sum(map(len, groups)), "mean_diff": m, "ci_lo": lo, "ci_hi": hi})
prim_df, stt_df, pooled_df = pd.DataFrame(prim), pd.DataFrame(stt), pd.DataFrame(pooled)
if fam_tasks:
    prim_df.to_csv(run / "family_primary.csv", index=False)
    stt_df.to_csv(run / "samples_to_target.csv", index=False)
    pooled_df.to_csv(run / "family_controls.csv", index=False)
    for t in fam_tasks.get("parity_hidden", []):
        print(h9_canary(t).replace("**", ""))

# ---- figures ------------------------------------------------------------------
(run / "figures").mkdir(exist_ok=True)
for task, g in summary.groupby("task"):
    fig, ax = plt.subplots(figsize=(6, 4))
    for arm, ga in g.groupby("arm"):
        ga = ga.sort_values("budget")
        ax.errorbar(ga["budget"], ga["mean_test_acc"],
                    yerr=[ga["mean_test_acc"] - ga["ci_lo"], ga["ci_hi"] - ga["mean_test_acc"]],
                    marker="o", capsize=3, label=arm)
    ax.set_xscale("symlog", linthresh=8)
    budgets = sorted(g["budget"].unique())
    ax.set_xticks(budgets)
    ax.set_xticklabels([str(b) for b in budgets])
    ax.set_xlabel("training examples (0 = no training)")
    ax.set_ylabel("test accuracy")
    ax.set_title(task)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(run / "figures" / f"{task}.png", dpi=150)
    plt.close(fig)

# ---- report -------------------------------------------------------------------
def fmt_mult(r):
    zero = r["budget"] == 0
    unit = " ex." if zero else "x"
    val = (lambda x: f"{x:.0f}") if zero else (lambda x: f"{x:.2f}")
    st = r["status"]
    if st == "ceiling":
        return "both at ceiling"
    if st == "chance":
        return "≈ chance (no multiplier)"
    if st == "below":
        return f"<= {val(r['mult_hi'] if not zero else r['n_eq_hi'])}{unit}"
    if st == "above":
        return f">= {val(r['mult_lo'] if not zero else r['n_eq_lo'])}{unit}"
    lo = r["n_eq_lo"] if zero else r["mult_lo"]
    hi = r["n_eq_hi"] if zero else r["mult_hi"]
    if st == "range":
        return f"{val(lo)}-{val(hi)}{unit} (random flat here)"
    pt = r["n_eq_point"] if zero else r["mult_point"]
    return (f"{'worth ' if zero else ''}{val(pt)}{unit} (CI {val(r['ci_lo'])}-{val(r['ci_hi'])}; "
            f"bracket {val(lo)}{unit}-{val(hi)}{unit})")


def fmt_n(n, c):
    return f"{c} {n:.0f}" if c else f"{n:.0f}"


def fmt_ratio(v, kind):
    if kind in ("undetermined", "not defined"):
        return "not defined (written needs no data)" if kind == "not defined" else "undetermined (both censored)"
    return f"{kind + ' ' if kind else ''}{v:.2f}x"


def family_section(fam: str, tasks: list[str]) -> list[str]:
    out = [f"## Family: {fam}", ""]
    if fam == "parity_hidden":
        out += [h9_canary(t) for t in tasks] + [""]
    p_ = prim_df[prim_df.family == fam] if not prim_df.empty else prim_df
    if len(p_):
        out += [f"**Primary:** written − random test accuracy at budgets {', '.join(map(str, a.primary_budgets))}, "
                "paired by seed, 95% bootstrap CI over seeds.", "", "| instance | arm | budget | seeds | written − random (95% CI) |",
                "|---|---|---|---|---|"]
        out += [f"| {r.task} | {r.arm} | {r.budget} | {r.n_seeds} | {r.mean_diff:+.3f} "
                f"({r.ci_lo:+.3f} to {r.ci_hi:+.3f}) |" for r in p_.itertuples()]
        for arm, g in p_.groupby("arm"):
            counts = ", ".join(f"{b}: {int((g[g.budget == b].ci_lo > 0).sum())} of {g[g.budget == b].task.nunique()}"
                               for b in a.primary_budgets)
            out += ["", f"Instances with CI lower bound > 0 ({arm}): {counts}."]
        out.append("")
    s_ = stt_df[(stt_df.family == fam) & (stt_df.arm.isin([a.random_arm, *written_arms(tasks)]))] \
        if not stt_df.empty else stt_df
    if len(s_):
        out += ["**Samples to target (B.8):** budget at which the arm's mean test accuracy reaches the target "
                "(log-linear on its own running-max curve; 0 = met zero-shot; `<= 16` = first met between 0 "
                "and 16; `>` = not met by the largest budget).", "",
                "| instance | target | arm | random n | arm n | random / arm |", "|---|---|---|---|---|---|"]
        for (t, target), g in s_.groupby(["task", "target"]):
            rand = g[g.arm == a.random_arm]
            rtxt = fmt_n(rand.n.iloc[0], rand.censor.iloc[0]) if len(rand) else "-"
            for r in g[g.arm != a.random_arm].itertuples():
                out.append(f"| {t} | {target} | {r.arm} | {rtxt} | {fmt_n(r.n, r.censor)} | "
                           f"{fmt_ratio(r.ratio_random_over_arm, r.ratio_kind) if len(rand) else '-'} |")
        out.append("")
    z = per_sample[per_sample.task.isin(tasks) & (per_sample.budget == 0)]
    if len(z):
        out += ["**Zero-shot test accuracy per sample and instance:**", "",
                "| arm | sample | " + " | ".join(tasks) + " |", "|---" * (2 + len(tasks)) + "|"]
        for (arm, sid), g in z.groupby(["arm", "sample_id"]):
            acc = g.set_index("task").mean_test_acc
            out.append(f"| {arm} | {sid} | " + " | ".join(f"{acc[t]:.3f}" if t in acc.index else "-" for t in tasks) + " |")
        for arm in written_arms(tasks):
            zs = summary[(summary.arm == arm) & (summary.budget == 0)].set_index("task").mean_test_acc
            out.append(f"| {arm} | mean | " + " | ".join(f"{zs[t]:.3f}" if t in zs.index else "-" for t in tasks) + " |")
        out.append("")
    cells = df[df.task.isin(tasks) & (df.kind == "written") & (df.budget == F1C_BUDGET)]
    if len(cells):
        out += [f"**Exploratory (F1c):** per sample, the (instance, seed) cells whose training run at budget "
                f"{F1C_BUDGET} reaches test accuracy >= {F1C_TARGET} (that one run, not the best of smaller budgets).",
                "", "| arm | sample | cells reaching | share |", "|---|---|---|---|"]
        for (arm, sid), g in cells.groupby(["arm", "sample_id"]):
            k = int((g.test_acc >= F1C_TARGET).sum())
            out.append(f"| {arm} | {sid} | {k} of {len(g)} | {k / len(g):.2f} |")
        out.append("")
    c_ = pooled_df[pooled_df.family == fam] if not pooled_df.empty else pooled_df
    if len(c_):
        out += ["**Controls pooled over instances (B.8 secondary 4):** A − B paired by seed; 95% CI from a "
                "bootstrap stratified by instance (seeds resampled within each instance, instances weighted "
                "equally). Only budgets measured in every instance are pooled.", "",
                "| test | A | B | budget | instances | pairs | A − B (95% CI) |", "|---|---|---|---|---|---|---|"]
        out += [f"| {r.test} | {r.arm_a} | {r.arm_b} | {r.budget} | {r.n_instances} | {r.n_pairs} | "
                f"{r.mean_diff:+.3f} ({r.ci_lo:+.3f} to {r.ci_hi:+.3f}) |" for r in c_.itertuples()]
        for src, g in c_[c_.test == "structure"].groupby("source"):
            g = g.set_index("budget")
            checks = ", ".join(f"{b}: {'yes' if g.ci_lo[b] > 0 else 'no'}" if b in g.index else f"{b}: not measured"
                               for b in H10_BUDGETS)
            out += ["", f"H10 check ({src}, structure CI lower bound > 0 at 16, 64 and 256): {checks}."]
        out.append("")
    return out


lines = [f"# Results: {run.name}", "",
         "Data multiplier = how many times more data the random-init arm needs to match this arm's mean "
         "test accuracy. Budget 0 rows give the init's worth in examples instead. Rules "
         f"(margin {a.margin}): '≈ chance' = within the margin of a majority-class predictor, so no "
         "multiplier; 'both at ceiling' = this arm and random both have mean test accuracy "
         f">= {CEILING} at this budget, so no multiplier; `>=` / `<=` = outside random's measured range; 'random flat here' = the random "
         "curve does not clearly rise between the bracketing budgets, so only the interval is known; "
         "otherwise a log-linear point estimate with its 95% bootstrap CI over seeds and the bracket "
         "it was interpolated in.", ""]
for fam, tasks in fam_tasks.items():  # Phase 2 families first: read the H9 canary, then the primary table
    lines += family_section(fam, tasks)
for task, g in summary.groupby("task"):
    chance_txt = ""
    if not mult_df.empty and (mult_df.task == task).any():
        chance_txt = f"Majority-class baseline: {mult_df[mult_df.task == task].chance_acc.iloc[0]:.3f}"
    canary = [h9_canary(task), ""] if family_of[task] == "parity_hidden" else []
    lines += [f"## {task}", "", *canary, f"![{task}](figures/{task}.png)", "", chance_txt, "",
              "| arm | budget | seeds | test acc (95% CI) | step-0 selected | data multiplier |",
              "|---|---|---|---|---|---|"]
    for _, r in g.iterrows():
        m = mult_df[(mult_df.task == task) & (mult_df.arm == r.arm) & (mult_df.budget == r.budget)] \
            if not mult_df.empty else mult_df
        ms = fmt_mult(m.iloc[0]) if len(m) else "-"
        lines.append(f"| {r.arm} | {r.budget} | {r.n_seeds} | {r.mean_test_acc:.3f} "
                     f"({r.ci_lo:.3f}-{r.ci_hi:.3f}) | {r.frac_selected_step0:.0%} | {ms} |")
    lines.append("")
    ps = per_sample[per_sample.task == task]
    if not ps.empty:
        budgets = sorted(ps.budget.unique())
        lines += ["**Per sample** (written arms; mean test accuracy, then mean test loss, over each sample's "
                  "seeds; n=0 = zero-shot. Loss shows margin differences that accuracy hides). Samples get "
                  "different seeds, so fine-tuned differences between samples also include seed "
                  "(training-set) variation:", "",
                  "| arm | sample | seeds | "
                  + " | ".join(f"{k} n={b}" for k in ("acc", "loss") for b in budgets) + " |",
                  "|---" * (3 + 2 * len(budgets)) + "|"]
        for (arm, sid), g in ps.groupby(["arm", "sample_id"]):
            gb = g.set_index("budget")
            cells = [f"{gb[col][b]:{fmt}}" if b in gb.index else "-"
                     for col, fmt in (("mean_test_acc", ".3f"), ("mean_test_loss", ".3g")) for b in budgets]
            lines.append(f"| {arm} | {sid} | {g.seeds.iloc[0]} | " + " | ".join(cells) + " |")
        lines.append("")
    if not comp_df.empty and (comp_df.task == task).any():
        lines += ["**Controls** (test-accuracy difference A - B, paired by seed, 95% bootstrap CI; "
                  "with few seeds the CI is rough):", "",
                  "| test | A | B | budget | seeds | A - B (95% CI) |", "|---|---|---|---|---|---|"]
        for _, c in comp_df[comp_df.task == task].iterrows():
            lines.append(f"| {c.test} | {c.arm_a} | {c.arm_b} | {c.budget} | {c.n_seeds} | "
                         f"{c.mean_diff:+.3f} ({c.ci_lo:+.3f} to {c.ci_hi:+.3f}) |")
        lines.append("")
(run / "report.md").write_text("\n".join(lines))
extra = ", family_primary.csv, samples_to_target.csv, family_controls.csv" if fam_tasks else ""
print(f"wrote {run / 'report.md'}, summary.csv, multipliers.csv, comparisons.csv, per_sample.csv{extra}, figures/")
