"""Sweep over (task, arm, budget, seed). Each job runs the full HP grid and
selects on validation, so every arm gets exactly the same tuning budget.

Design choices (see docs/DECISIONS.md):
  * Paired: for a given seed, all arms see the same training examples.
  * Nested: the budget-n training set is the first n examples of one fixed
    per-seed pool, so larger budgets strictly add data.
  * Validation and test sets are fixed across seeds, arms and budgets.
"""

from __future__ import annotations

import itertools
import json
import multiprocessing
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import yaml

from . import seeding
from .init_arms import (add_noise, init_random, load_weights, norm_matched, shuffle_within_tensors,
                        written_samples)
from .models import evaluate
from .tasks import get_task
from .train import TrainConfig, train


@dataclass
class Arm:
    name: str
    kind: str  # random | written | written_noise | shuffled_noise | norm_matched | shuffled
    source: str | None = None
    alpha: float = 0.1  # written_noise and shuffled_noise


@dataclass
class SweepConfig:
    tasks: list[str]
    arms: list[Arm]
    budgets: list[int]
    seeds: list[int]
    lr: list[float]
    weight_decay: list[float]
    muon_lr: list[float | None] = field(default_factory=lambda: [None])
    optimizer: str = "adamw"
    batch_size: int = 64
    max_steps: int = 3000
    eval_every: int = 50
    patience: int = 10
    val_size: int = 256
    test_size: int = 2000
    workers: int = 0  # 0 = os.cpu_count()
    require_audited: bool = False  # only use written samples marked audited in meta.json

    @classmethod
    def load(cls, path: str | Path) -> "SweepConfig":
        raw = yaml.safe_load(Path(path).read_text())
        raw["arms"] = [Arm(**a) for a in raw["arms"]]
        return cls(**raw)


def job_key(task: str, arm: str, budget: int, seed: int) -> str:
    return f"{task}|{arm}|{budget}|{seed}"


def _fixed_split(task, split: str, size: int):
    if hasattr(task, "split_size"):
        size = min(size, task.split_size(split))
    return task.sample(size, seeding.rng(0, f"{split}_data"), split)


def effective_budgets(task, budgets: list[int]) -> list[int]:
    """A.4 pool rule: a budget above the task's training pool becomes the pool size, and a budget
    that ends up duplicated is dropped. Job keys use these actual budgets."""
    out: list[int] = []
    for b in budgets:
        b = b if task.max_train_pool is None else min(b, task.max_train_pool)
        if b not in out:
            out.append(b)
    return out


def _train_pool(task, seed: int, max_budget: int):
    n = max_budget if task.max_train_pool is None else min(max_budget, task.max_train_pool)
    return task.sample(n, seeding.rng(seed, "train_data"), "train")


def build_init(task, arm: Arm, seed: int, require_audited: bool = False):
    """Return (params, sample_id or None), or None if the arm has no weights for this task."""
    if arm.kind == "random":
        return init_random(task, seeding.rng(seed, "init")), None
    files = written_samples(task.family, arm.source, require_audited)
    if not files:
        return None
    f = files[seed % len(files)]
    params = load_weights(task, f)
    sid = f.parent.name
    if arm.kind == "written":
        return params, sid
    if arm.kind == "written_noise":
        return add_noise(task, params, arm.alpha, seeding.rng(seed, "noise", arm.name)), sid
    if arm.kind == "shuffled":
        return shuffle_within_tensors(params, seeding.rng(seed, "shuffle", arm.name)), sid
    if arm.kind == "shuffled_noise":
        shuffled = shuffle_within_tensors(params, seeding.rng(seed, "shuffle", arm.name))
        return add_noise(task, shuffled, arm.alpha, seeding.rng(seed, "noise", arm.name)), sid
    if arm.kind == "norm_matched":
        return norm_matched(params, seeding.rng(seed, "norm", arm.name)), sid
    raise ValueError(f"unknown arm kind {arm.kind!r}")


def run_job(cfg: SweepConfig, task_name: str, arm: Arm, budget: int, seed: int) -> dict | None:
    t0 = time.time()
    task = get_task(task_name)
    built = build_init(task, arm, seed, cfg.require_audited)
    if built is None:
        return None
    init, sample_id = built
    Xte, yte = _fixed_split(task, "test", cfg.test_size)
    Xva, yva = _fixed_split(task, "val", cfg.val_size)
    init_test_acc, init_test_loss = evaluate(init, Xte, yte, task.activation)
    majority_acc = float(np.bincount(yte).max() / len(yte))

    row = {
        "key": job_key(task_name, arm.name, budget, seed),
        "task": task_name, "arm": arm.name, "kind": arm.kind, "source": arm.source,
        "sample_id": sample_id, "budget": budget, "seed": seed,
        "init_test_acc": init_test_acc, "init_test_loss": init_test_loss,
        "test_majority_acc": majority_acc,
    }
    if budget == 0:
        row.update(test_acc=init_test_acc, test_loss=init_test_loss, hp=None, hp_results=[],
                   best_step=0, seconds=time.time() - t0)
        return row

    pool_X, pool_y = _train_pool(task, seed, max(cfg.budgets))
    Xtr, ytr = pool_X[:budget], pool_y[:budget]

    results = []
    for lr, wd, mlr in itertools.product(cfg.lr, cfg.weight_decay, cfg.muon_lr):
        tc = TrainConfig(optimizer=cfg.optimizer, lr=lr, weight_decay=wd, muon_lr=mlr,
                         batch_size=cfg.batch_size, max_steps=cfg.max_steps,
                         eval_every=cfg.eval_every, patience=cfg.patience)
        hp_tag = f"{lr}-{wd}-{mlr}"
        params, info = train(init, task.activation, Xtr, ytr, Xva, yva, tc,
                             seeding.rng(seed, "minibatch", hp_tag))
        te_acc, te_loss = evaluate(params, Xte, yte, task.activation)
        results.append({"lr": lr, "weight_decay": wd, "muon_lr": mlr, **info,
                        "test_acc": te_acc, "test_loss": te_loss})

    best = max(results, key=lambda r: (r["val_acc"], -r["val_loss"]))
    row.update(test_acc=best["test_acc"], test_loss=best["test_loss"],
               hp={"lr": best["lr"], "weight_decay": best["weight_decay"], "muon_lr": best["muon_lr"]},
               best_step=best["best_step"], val_acc=best["val_acc"], hp_results=results,
               seconds=time.time() - t0)
    return row


def _worker(args):
    cfg, task_name, arm, budget, seed = args
    return run_job(cfg, task_name, arm, budget, seed)


def _init_worker():
    os.environ.setdefault("OMP_NUM_THREADS", "1")


def run_sweep(cfg: SweepConfig, out_dir: Path, verbose: bool = True) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    runs_path = out_dir / "runs.jsonl"
    done = set()
    if runs_path.exists():
        for line in runs_path.read_text().splitlines():
            if line.strip():
                done.add(json.loads(line)["key"])

    jobs, skipped = [], []
    for t in cfg.tasks:
        task = get_task(t)
        for arm, b, s in itertools.product(cfg.arms, effective_budgets(task, cfg.budgets), cfg.seeds):
            if arm.kind != "random" and not written_samples(task.family, arm.source, cfg.require_audited):
                skipped.append((t, arm.name))
                continue
            if job_key(t, arm.name, b, s) not in done:
                jobs.append((cfg, t, arm, b, s))

    for t, a in sorted(set(skipped)):
        print(f"[skip] {t}: no usable weights for arm {a!r} "
              f"(missing, failed, or not audited while require_audited is on)")
    if verbose:
        print(f"{len(jobs)} jobs to run ({len(done)} already done) -> {runs_path}")

    workers = cfg.workers or os.cpu_count() or 1
    with open(runs_path, "a") as fh:
        if workers == 1:
            for i, j in enumerate(jobs, 1):
                _write(fh, _worker(j), i, len(jobs), verbose)
        else:
            # Always "spawn" (the macOS default) so every OS behaves the same and
            # tests on Linux catch spawn-only bugs.
            ctx = multiprocessing.get_context("spawn")
            with ProcessPoolExecutor(max_workers=workers, mp_context=ctx, initializer=_init_worker) as ex:
                futs = [ex.submit(_worker, j) for j in jobs]
                for i, f in enumerate(as_completed(futs), 1):
                    _write(fh, f.result(), i, len(jobs), verbose)
    return runs_path


def _write(fh, row, i, n, verbose):
    if row is None:
        return
    fh.write(json.dumps(row) + "\n")
    fh.flush()
    if verbose:
        print(f"[{i}/{n}] {row['key']}: test_acc={row['test_acc']:.3f} "
              f"(init {row['init_test_acc']:.3f}, {row['seconds']:.1f}s)")


def config_to_dict(cfg: SweepConfig) -> dict:
    return asdict(cfg)
