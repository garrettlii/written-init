from __future__ import annotations

import hashlib
import string

from ..experiment import SweepConfig
from ..paths import PROMPTS
from ..tasks import Task
from . import WRITABLE

_DELIVER_FILE = (
    "Write your complete solution to `build.py` in this folder (it contains a stub to replace). "
    "Also write `NOTES.md` with a short explanation of the algorithm your network implements and how "
    "each layer computes it. When you are done, reply with a one-line summary."
)
_DELIVER_REPLY = (
    "Reply with a short explanation of the algorithm your network implements and how each layer "
    "computes it, then exactly one ```python code block containing the complete build.py, which "
    "defines `build_weights()`."
)


_OPTIMIZER_NAMES = {"adamw": "AdamW"}


def objective_values(cfg: SweepConfig) -> dict[str, str]:
    """Placeholders of objectives that describe fine-tuning (PHASE2_PLAN B.6), from the sweep config,
    so the prompt can't drift from the protocol. Readable rendering: display name, sets in braces."""
    if cfg.optimizer not in _OPTIMIZER_NAMES:
        raise ValueError(f"no display name for optimizer {cfg.optimizer!r}; add one to _OPTIMIZER_NAMES")
    grid = lambda xs: "{" + ", ".join(str(float(x)) for x in xs) + "}"
    return {"optimizer": _OPTIMIZER_NAMES[cfg.optimizer], "batch_size": str(int(cfg.batch_size)),
            "max_steps": str(int(cfg.max_steps)), "lr_grid": grid(cfg.lr), "wd_grid": grid(cfg.weight_decay)}


def objective_text(objective: str, cfg: SweepConfig | None = None) -> str:
    obj = PROMPTS / "objectives" / f"{objective}.md"
    if not obj.exists():
        raise ValueError(f"unknown objective {objective!r}; known: {objectives()}")
    text = obj.read_text().strip()
    if any(field for _, field, _, _ in string.Formatter().parse(text)):
        if cfg is None:
            raise ValueError(f"objective {objective!r} has placeholders: pass the sweep config (--config)")
        text = text.format(**objective_values(cfg))
    return text


def objectives() -> list[str]:
    return sorted(p.stem for p in (PROMPTS / "objectives").glob("*.md"))


def task_prompt(task: Task, agent: str, condition: str, objective: str = "zero_shot",
                cfg: SweepConfig | None = None) -> str:
    return (PROMPTS / "agent_task.md").read_text().format(
        system=(PROMPTS / "system.md").read_text().strip(),
        task_spec=task.task_spec(),
        arch_spec=task.arch_spec(),
        objective=objective_text(objective, cfg),
        tools=(PROMPTS / "conditions" / f"{agent}_{condition}.md").read_text().strip(),
        deliverable=_DELIVER_FILE if (agent, condition) in WRITABLE else _DELIVER_REPLY,
    ).strip()


def retry_section(error: str, writable: bool) -> str:
    where = "Your previous build.py is still in this folder. " if writable else ""
    return (PROMPTS / "retry.md").read_text().format(error=error, where=where).strip()


def prompt_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]
