"""Plain-numpy MLP: forward pass, softmax cross-entropy, and backprop.

Weights are (fan_in, fan_out), matching the convention the LLM is told:
    h_{i+1} = act(h_i @ W_i + b_i), logits = h_{L-1} @ W_{L-1} + b_{L-1}
Everything is float64; these networks are tiny and exact gradients are worth
more than speed. tests/test_models.py checks gradients by finite differences.
"""

from __future__ import annotations

import numpy as np

Params = dict[str, np.ndarray]


def _act(name: str, z: np.ndarray) -> np.ndarray:
    if name == "relu":
        return np.maximum(z, 0.0)
    if name == "tanh":
        return np.tanh(z)
    raise ValueError(name)


def _act_grad(name: str, z: np.ndarray) -> np.ndarray:
    if name == "relu":
        return (z > 0).astype(z.dtype)
    if name == "tanh":
        return 1.0 - np.tanh(z) ** 2
    raise ValueError(name)


def n_layers(params: Params) -> int:
    return sum(1 for k in params if k.startswith("W"))


def logits(params: Params, X: np.ndarray, activation: str) -> np.ndarray:
    L = n_layers(params)
    h = X
    for i in range(L):
        z = h @ params[f"W{i}"] + params[f"b{i}"]
        h = _act(activation, z) if i < L - 1 else z
    return h


def softmax_xent(z: np.ndarray, y: np.ndarray) -> tuple[float, np.ndarray]:
    """Mean cross-entropy and its gradient w.r.t. logits."""
    z = z - z.max(axis=1, keepdims=True)
    logp = z - np.log(np.exp(z).sum(axis=1, keepdims=True))
    n = len(y)
    loss = -logp[np.arange(n), y].mean()
    d = np.exp(logp)
    d[np.arange(n), y] -= 1.0
    return float(loss), d / n


def loss_and_grads(params: Params, X: np.ndarray, y: np.ndarray, activation: str) -> tuple[float, Params]:
    L = n_layers(params)
    hs, zs = [X], []
    h = X
    for i in range(L):
        z = h @ params[f"W{i}"] + params[f"b{i}"]
        zs.append(z)
        h = _act(activation, z) if i < L - 1 else z
        hs.append(h)
    loss, d = softmax_xent(zs[-1], y)
    grads: Params = {}
    for i in reversed(range(L)):
        grads[f"W{i}"] = hs[i].T @ d
        grads[f"b{i}"] = d.sum(axis=0)
        if i > 0:
            d = (d @ params[f"W{i}"].T) * _act_grad(activation, zs[i - 1])
    return loss, grads


def evaluate(params: Params, X: np.ndarray, y: np.ndarray, activation: str) -> tuple[float, float]:
    """Return (accuracy, mean cross-entropy)."""
    z = logits(params, X, activation)
    loss, _ = softmax_xent(z, y)
    acc = float((z.argmax(axis=1) == y).mean())
    return acc, loss


def copy_params(params: Params) -> Params:
    return {k: v.copy() for k, v in params.items()}
