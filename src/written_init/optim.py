"""Optimizers in numpy: AdamW, and a Muon hybrid for the optional extension.

Muon here follows the public reference recipe (Newton-Schulz orthogonalized
momentum on hidden 2D weights; AdamW for first/last layers and biases). It is
lightly tested only. Verify it against a reference implementation before
reporting any Muon result.
"""

from __future__ import annotations

import numpy as np

from .models import Params


class AdamW:
    def __init__(self, params: Params, lr: float, weight_decay: float, betas=(0.9, 0.999), eps=1e-8,
                 only: set[str] | None = None):
        self.lr, self.wd, self.b1, self.b2, self.eps = lr, weight_decay, betas[0], betas[1], eps
        self.keys = [k for k in params if only is None or k in only]
        self.m = {k: np.zeros_like(params[k]) for k in self.keys}
        self.v = {k: np.zeros_like(params[k]) for k in self.keys}
        self.t = 0

    def step(self, params: Params, grads: Params) -> None:
        self.t += 1
        c1 = 1 - self.b1**self.t
        c2 = 1 - self.b2**self.t
        for k in self.keys:
            g = grads[k]
            self.m[k] = self.b1 * self.m[k] + (1 - self.b1) * g
            self.v[k] = self.b2 * self.v[k] + (1 - self.b2) * g * g
            if self.wd and k.startswith("W"):  # decoupled decay on weights only
                params[k] *= 1 - self.lr * self.wd
            params[k] -= self.lr * (self.m[k] / c1) / (np.sqrt(self.v[k] / c2) + self.eps)


def newton_schulz5(G: np.ndarray, steps: int = 5, eps: float = 1e-7) -> np.ndarray:
    """Approximately orthogonalize G (pushes singular values toward ~1)."""
    a, b, c = 3.4445, -4.7750, 2.0315
    X = G / (np.linalg.norm(G) + eps)
    transposed = X.shape[0] > X.shape[1]
    if transposed:
        X = X.T
    for _ in range(steps):
        A = X @ X.T
        X = a * X + (b * A + c * A @ A) @ X
    return X.T if transposed else X


class MuonHybrid:
    """Muon on hidden-to-hidden weights, AdamW on everything else."""

    def __init__(self, params: Params, lr: float, weight_decay: float, muon_lr: float,
                 momentum: float = 0.95, **adam_kw):
        L = sum(1 for k in params if k.startswith("W"))
        self.muon_keys = [f"W{i}" for i in range(1, L - 1)]
        rest = {k for k in params if k not in self.muon_keys}
        self.adam = AdamW(params, lr, weight_decay, only=rest, **adam_kw)
        self.muon_lr, self.wd, self.mu = muon_lr, weight_decay, momentum
        self.buf = {k: np.zeros_like(params[k]) for k in self.muon_keys}

    def step(self, params: Params, grads: Params) -> None:
        self.adam.step(params, grads)
        for k in self.muon_keys:
            g = grads[k]
            self.buf[k] = self.mu * self.buf[k] + g
            u = newton_schulz5(g + self.mu * self.buf[k])  # Nesterov
            fan_in, fan_out = params[k].shape
            scale = max(1.0, fan_out / fan_in) ** 0.5
            if self.wd:
                params[k] *= 1 - self.muon_lr * self.wd
            params[k] -= self.muon_lr * scale * u


def make_optimizer(name: str, params: Params, lr: float, weight_decay: float, muon_lr: float | None = None):
    if name == "adamw":
        return AdamW(params, lr, weight_decay)
    if name == "muon":
        if muon_lr is None:
            raise ValueError("muon needs muon_lr")
        return MuonHybrid(params, lr, weight_decay, muon_lr)
    raise ValueError(f"unknown optimizer {name!r}")
