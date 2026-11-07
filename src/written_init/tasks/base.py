"""Task interface.

A task defines (1) a data distribution, (2) a fixed MLP architecture, and
(3) a natural-language spec that is the ONLY information the LLM gets when
writing weights. Keep spec() precise: anything the LLM needs to know about the
input encoding must be in it, and nothing derived from sampled data may be.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np


class Task(ABC):
    name: str
    in_dim: int
    out_dim: int
    hidden: list[int]
    activation: str = "relu"  # "relu" or "tanh"
    # Upper bound on unique training examples this task can supply (None = unlimited).
    max_train_pool: int | None = None

    @property
    def family(self) -> str:
        """Folder under inits/ that holds written samples for this task. Phase 2 instances
        override it with their family's name, so one sample serves every instance."""
        return self.name

    # ---- data ---------------------------------------------------------------
    @abstractmethod
    def sample(self, n: int, rng: np.random.Generator, split: str) -> tuple[np.ndarray, np.ndarray]:
        """Return X (n, in_dim) float64 and y (n,) int64. split in {train, val, test}."""

    # ---- spec given to the LLM ---------------------------------------------
    @abstractmethod
    def task_spec(self) -> str:
        """Natural-language description of inputs, labels and class ids."""

    # ---- architecture -------------------------------------------------------
    @property
    def layer_sizes(self) -> list[int]:
        return [self.in_dim, *self.hidden, self.out_dim]

    @property
    def n_layers(self) -> int:
        return len(self.layer_sizes) - 1

    def param_shapes(self) -> dict[str, tuple[int, ...]]:
        s = self.layer_sizes
        shapes: dict[str, tuple[int, ...]] = {}
        for i in range(self.n_layers):
            shapes[f"W{i}"] = (s[i], s[i + 1])
            shapes[f"b{i}"] = (s[i + 1],)
        return shapes

    def n_params(self) -> int:
        return int(sum(np.prod(v) for v in self.param_shapes().values()))

    def arch_spec(self) -> str:
        s = self.layer_sizes
        L = self.n_layers
        act = self.activation
        lines = [
            f"Layer sizes: {s} ({self.n_params():,} parameters total).",
            "Forward pass (x is a row vector of length "
            f"{s[0]}; weights are stored as (fan_in, fan_out)):",
            "    h0 = x",
        ]
        for i in range(L - 1):
            lines.append(f"    h{i + 1} = {act}(h{i} @ W{i} + b{i})")
        lines.append(f"    logits = h{L - 1} @ W{L - 1} + b{L - 1}")
        lines.append("    prediction = argmax(logits)")
        if act == "relu":
            lines.append("relu(z) = max(z, 0), applied elementwise.")
        else:
            lines.append("tanh is applied elementwise.")
        lines.append("Parameters you must return (name: shape):")
        for k, v in self.param_shapes().items():
            lines.append(f"    {k}: {v}")
        return "\n".join(lines)


class PartitionedTask(Task):
    """For tasks with a finite input set: partition it once into disjoint
    test / val / train pools so no test input is ever trained on."""

    _parts: dict[str, tuple[np.ndarray, np.ndarray]]

    def _partition(self, X: np.ndarray, y: np.ndarray, n_test: int, n_val: int, split_seed: int) -> None:
        perm = np.random.default_rng(split_seed).permutation(len(y))
        X, y = X[perm], y[perm]
        self._parts = {
            "test": (X[:n_test], y[:n_test]),
            "val": (X[n_test:n_test + n_val], y[n_test:n_test + n_val]),
            "train": (X[n_test + n_val:], y[n_test + n_val:]),
        }
        self.max_train_pool = len(self._parts["train"][1])

    def sample(self, n, rng, split):
        X, y = self._parts[split]
        if n > len(y):
            raise ValueError(f"{split} split has {len(y)} examples, asked for {n}")
        idx = rng.permutation(len(y))[:n]
        return X[idx], y[idx]

    def split_size(self, split: str) -> int:
        return len(self._parts[split][1])
