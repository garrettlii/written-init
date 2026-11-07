"""Initialization arms.

random          standard He (relu) / Xavier (tanh) init, zero biases
written         LLM-written weights, exactly as produced
written_noise   written + small Gaussian noise on weights (revives dead units)
shuffled_noise  written entries permuted within each tensor, THEN the same
                noise as written_noise. Primary structure control: compare
                written_noise vs shuffled_noise. Both start equally trainable
                and differ only in the arrangement of the written values.
norm_matched    random Gaussian directions rescaled so every tensor has the
                written tensor's Frobenius norm. Scale control: same per-tensor
                magnitude as written, no sparsity, no structure.
shuffled        written entries permuted within each tensor, no noise.
                SECONDARY only: written inits are mostly zeros, so a shuffled
                copy leaves most ReLU units with zero input and zero bias,
                exactly where the ReLU gradient is 0. Those units never update,
                so this arm can lose to random for reasons unrelated to
                structure (seen in the smoke run on sparse_parity).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .models import Params
from .paths import INITS
from .tasks import Task


def init_random(task: Task, rng: np.random.Generator) -> Params:
    params: Params = {}
    for k, shape in task.param_shapes().items():
        if k.startswith("W"):
            fan_in, fan_out = shape
            std = np.sqrt(2.0 / fan_in) if task.activation == "relu" else np.sqrt(2.0 / (fan_in + fan_out))
            params[k] = rng.normal(0.0, std, size=shape)
        else:
            params[k] = np.zeros(shape)
    return params


def written_samples(task_name: str, source: str, require_audited: bool = False) -> list[Path]:
    """All usable weight files for a (task, source), sorted by sample id.

    With require_audited, only samples whose meta.json says "audited": true
    (set after a human/agent review of build.py, see /audit-init) are used."""
    files = sorted((INITS / task_name / source).glob("sample_*/weights.npz"))
    if require_audited:
        files = [f for f in files if _is_audited(f.parent)]
    return files


def _is_audited(sample_dir: Path) -> bool:
    meta = sample_dir / "meta.json"
    if not meta.exists():
        return False
    return bool(json.loads(meta.read_text()).get("audited", False))


def load_weights(task: Task, path: Path) -> Params:
    with np.load(path) as f:
        params = {k: f[k].astype(np.float64) for k in f.files}
    validate(task, params)
    return params


def validate(task: Task, params: Params) -> None:
    expected = task.param_shapes()
    if set(params) != set(expected):
        raise ValueError(f"param names {sorted(params)} != expected {sorted(expected)}")
    for k, shape in expected.items():
        if tuple(params[k].shape) != tuple(shape):
            raise ValueError(f"{k}: shape {params[k].shape} != expected {shape}")
        if not np.all(np.isfinite(params[k])):
            raise ValueError(f"{k}: non-finite values")


def add_noise(task: Task, params: Params, alpha: float, rng: np.random.Generator) -> Params:
    out = {k: v.copy() for k, v in params.items()}
    for k, shape in task.param_shapes().items():
        if k.startswith("W"):
            fan_in, fan_out = shape
            std = np.sqrt(2.0 / fan_in) if task.activation == "relu" else np.sqrt(2.0 / (fan_in + fan_out))
            out[k] += alpha * std * rng.normal(size=shape)
    return out


def shuffle_within_tensors(params: Params, rng: np.random.Generator) -> Params:
    return {k: rng.permutation(v.ravel()).reshape(v.shape) for k, v in params.items()}


def norm_matched(params: Params, rng: np.random.Generator) -> Params:
    """Random directions with the written per-tensor Frobenius norms (zero stays zero)."""
    out: Params = {}
    for k, v in params.items():
        norm = float(np.linalg.norm(v))
        if norm == 0.0:
            out[k] = np.zeros_like(v)
        else:
            g = rng.normal(size=v.shape)
            out[k] = g * (norm / np.linalg.norm(g))
    return out
