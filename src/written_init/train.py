"""Training loop with early stopping on a held-out validation set.

Step 0 (the initialization itself) is an eligible checkpoint, so if training
only hurts a good written init, validation can pick "don't train". Selection is
by validation accuracy, ties broken by validation loss.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .models import Params, copy_params, evaluate, loss_and_grads
from .optim import make_optimizer


@dataclass
class TrainConfig:
    optimizer: str = "adamw"
    lr: float = 1e-3
    weight_decay: float = 0.0
    muon_lr: float | None = None
    batch_size: int = 64
    max_steps: int = 3000
    eval_every: int = 50
    patience: int = 10  # in evals


def train(params: Params, activation: str, Xtr, ytr, Xval, yval, cfg: TrainConfig,
          rng: np.random.Generator) -> tuple[Params, dict]:
    params = copy_params(params)
    opt = make_optimizer(cfg.optimizer, params, cfg.lr, cfg.weight_decay, cfg.muon_lr)
    n = len(ytr)
    bs = min(cfg.batch_size, n)

    val_acc, val_loss = evaluate(params, Xval, yval, activation)
    best = (val_acc, -val_loss)
    best_params, best_step = copy_params(params), 0
    since_best = 0
    diverged = False

    for step in range(1, cfg.max_steps + 1):
        idx = rng.choice(n, size=bs, replace=False) if bs < n else np.arange(n)
        loss, grads = loss_and_grads(params, Xtr[idx], ytr[idx], activation)
        if not np.isfinite(loss):
            diverged = True
            break
        opt.step(params, grads)

        if step % cfg.eval_every == 0 or step == cfg.max_steps:
            val_acc, val_loss = evaluate(params, Xval, yval, activation)
            score = (val_acc, -val_loss)
            if score > best:
                best, best_params, best_step, since_best = score, copy_params(params), step, 0
            else:
                since_best += 1
                if since_best >= cfg.patience:
                    break

    info = {
        "best_step": best_step,
        "steps_run": step,
        "val_acc": best[0],
        "val_loss": -best[1],
        "diverged": diverged,
    }
    return best_params, info
