"""Run scripts/analyze.py on a tiny synthetic run: ceiling status and per-sample table."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def _row(arm, kind, budget, seed, acc, sample_id=None):  # test_loss = 1 - acc, enough to check the column
    return {"task": "ring2d", "arm": arm, "kind": kind, "source": None if kind == "random" else "src",
            "sample_id": sample_id, "budget": budget, "seed": seed, "test_acc": acc, "test_loss": 1 - acc,
            "test_majority_acc": 0.5, "best_step": 0}


def test_ceiling_and_per_sample(tmp_path):
    rand = {0: 0.5, 16: 0.7, 64: 0.996}
    rows = [_row("random", "random", b, s, acc) for b, acc in rand.items() for s in (0, 1)]
    # sample_00 gets seed 0, sample_01 seed 1; sample_01 is weaker zero-shot.
    written = {0: (0.99, 0.80), 16: (0.99, 0.90), 64: (1.0, 0.998)}
    rows += [_row("opus", "written", b, s, accs[s], f"sample_0{s}") for b, accs in written.items() for s in (0, 1)]
    (tmp_path / "runs.jsonl").write_text("\n".join(json.dumps(r) for r in rows))

    env = {**os.environ, "PYTHONPATH": str(ROOT / "src") + os.pathsep + os.environ.get("PYTHONPATH", "")}
    proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "analyze.py"), str(tmp_path)],
                          capture_output=True, text=True, timeout=300, env=env)
    assert proc.returncode == 0, proc.stderr[-2000:]

    mult = pd.read_csv(tmp_path / "multipliers.csv").set_index("budget")
    assert mult.loc[64, "status"] == "ceiling"      # both means >= 0.995
    assert mult.loc[16, "status"] != "ceiling"      # arm mean 0.945, random 0.7
    assert mult.loc[0, "status"] != "ceiling"       # random has no budget-0 point on its curve

    ps = pd.read_csv(tmp_path / "per_sample.csv")
    assert len(ps) == 6 and set(ps.sample_id) == {"sample_00", "sample_01"}
    zs = ps[ps.budget == 0].set_index("sample_id").mean_test_acc
    assert zs["sample_00"] == 0.99 and zs["sample_01"] == 0.80

    report = (tmp_path / "report.md").read_text()
    assert "| opus | 64 | 2 | 0.999 (0.998-1.000) | 100% | both at ceiling |" in report
    assert "| opus | sample_01 | 1 | 0.800 | 0.900 | 0.998 | 0.2 | 0.1 | 0.002 |" in report


def test_phase2_family_sections(tmp_path):
    """Family section first, H9 canary flags a single out-of-band sample, primary counts, samples to
    target with censoring, and controls pooled over instances (PHASE2_PLAN B.8, B.9, B.12 #11)."""
    rows = []
    for i in range(3):
        task = f"parity_hidden_i{i}"
        for s in range(6):
            sid = f"sample_0{s % 3}"
            def row(arm, kind, budget, acc):
                r = _row(arm, kind, budget, s, acc, None if kind == "random" else sid)
                return {**r, "task": task}
            zs = 0.60 if (i == 1 and sid == "sample_01") else 0.50   # one leaky-looking sample on i1
            rows += [row("random", "random", 0, 0.50), row("random", "random", 16, 0.50 + 0.01 * s),
                     row("random", "random", 64, 0.60 + 0.01 * s),
                     row("opus", "written", 0, zs), row("opus", "written", 16, 0.70 + 0.01 * s),
                     row("opus", "written", 64, 0.97 + 0.001 * s)]
            for arm, kind, bump in (("opus_noise", "written_noise", 0.1), ("opus_shuffled_noise", "shuffled_noise", 0.0),
                                    ("opus_norm_matched", "norm_matched", 0.0)):
                rows += [row(arm, kind, b, 0.5 + bump + 0.01 * s) for b in (16, 64)]
    (tmp_path / "runs.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src") + os.pathsep + os.environ.get("PYTHONPATH", "")}
    proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "analyze.py"), str(tmp_path)],
                          capture_output=True, text=True, timeout=300, env=env)
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert "OUTSIDE" in proc.stdout  # canary also printed

    report = (tmp_path / "report.md").read_text()
    assert report.index("## Family: parity_hidden") < report.index("## parity_hidden_i0")
    canary = [l for l in report.splitlines() if l.startswith("**H9 canary (parity_hidden_i1)")]
    assert canary and "sample_01 0.600 (OUTSIDE)" in canary[0] and "possible leak" in canary[0]
    assert "opus mean 0.533" in canary[0]   # the mean alone (0.533) is inside the band: the sample decides
    assert "**H9 canary (parity_hidden_i0):** written zero-shot opus mean 0.500" in report
    assert "within 0.5 ± 0.04 (mean and every sample)" in report
    assert "| parity_hidden_i0 | opus | 16 | 6 | +0.200 (+0.200 to +0.200) |" in report
    assert "Instances with CI lower bound > 0 (opus): 16: 3 of 3, 64: 3 of 3." in report
    # written first reaches 0.95 between 16 (0.725) and 64 (0.9725); random never does (> 64)
    stt = pd.read_csv(tmp_path / "samples_to_target.csv")
    w = stt[(stt.task == "parity_hidden_i0") & (stt.arm == "opus") & (stt.target == 0.95)].iloc[0]
    assert w.censor != w.censor and 16 < w.n < 64 and w.ratio_kind == ">="   # NaN censor = exact
    assert "| parity_hidden_i0 | 0.95 | opus | > 64 |" in report
    pooled = pd.read_csv(tmp_path / "family_controls.csv")
    st = pooled[(pooled.test == "structure") & (pooled.budget == 16)].iloc[0]
    assert st.n_instances == 3 and st.n_pairs == 18 and abs(st.mean_diff - 0.1) < 1e-12
    assert "H10 check (src, structure CI lower bound > 0 at 16, 64 and 256): 16: yes, 64: yes, 256: not measured." in report
    proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "analyze.py"), str(tmp_path), "--primary-budgets", "64"],
                          capture_output=True, text=True, timeout=300, env=env)   # F1a reads one budget
    report = (tmp_path / "report.md").read_text()
    assert proc.returncode == 0 and "Instances with CI lower bound > 0 (opus): 64: 3 of 3." in report
    assert "| parity_hidden_i0 | opus | 16 |" not in report


def test_f1c_cell_share(tmp_path):
    """Per sample, cells reaching >= 0.95 at budget 128 itself; 192 doesn't count (PHASE2_PLAN F1c)."""
    rows = []
    for i in range(2):
        for s in range(6):
            sid = f"sample_0{s % 3}"
            at128 = {"sample_00": 0.96, "sample_01": 0.95 if (i, s) == (0, 1) else 0.90, "sample_02": 0.94}[sid]
            for b, acc in ((0, 0.5), (16, 0.6), (128, at128), (192, 1.0)):
                rows += [{**_row("random", "random", b, s, 0.5 + b / 1000), "task": f"parity_hidden_i{i}"},
                         {**_row("opus", "written", b, s, acc, sid), "task": f"parity_hidden_i{i}"}]
    (tmp_path / "runs.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src") + os.pathsep + os.environ.get("PYTHONPATH", "")}
    proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "analyze.py"), str(tmp_path)],
                          capture_output=True, text=True, timeout=300, env=env)
    assert proc.returncode == 0, proc.stderr[-2000:]
    report = (tmp_path / "report.md").read_text()
    assert "| opus | sample_00 | 4 of 4 | 1.00 |" in report
    assert "| opus | sample_01 | 1 of 4 | 0.25 |" in report   # exactly 0.95 counts
    assert "| opus | sample_02 | 0 of 4 | 0.00 |" in report
