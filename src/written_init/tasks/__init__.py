from functools import partial

from .base import Task
from .digits import Digits8x8
from .gridnav import GridNav
from .hidden import N_INSTANCES, GridNavHidden, ParityHidden, RingHidden
from .ring2d import Ring2D
from .sparse_parity import SparseParity

_PHASE1 = {
    "sparse_parity": SparseParity,
    "ring2d": Ring2D,
    "gridnav": GridNav,
    "digits8x8": Digits8x8,
}
# Phase 2 families (docs/PHASE2_PLAN.md). Agents write one init per family; it is evaluated on
# each instance task <family>_i<k>.
FAMILIES = {"parity_hidden": ParityHidden, "ring_hidden": RingHidden, "gridnav_hidden": GridNavHidden}

_REGISTRY = {
    **_PHASE1,
    **{f"{f}_i{i}": partial(cls, i) for f, cls in FAMILIES.items() for i in range(N_INSTANCES[f])},
}

_CACHE: dict[str, Task] = {}


def get_task(name: str) -> Task:
    if name not in _REGISTRY:
        raise KeyError(f"unknown task {name!r}; known: {sorted(_REGISTRY)}")
    if name not in _CACHE:
        _CACHE[name] = _REGISTRY[name]()
    return _CACHE[name]


def task_names() -> list[str]:
    return list(_REGISTRY)


def family_instances(family: str) -> list[str]:
    return [f"{family}_i{i}" for i in range(N_INSTANCES[family])]


def generation_targets() -> list[str]:
    """What an agent writes an init for: a Phase 1 task or a Phase 2 family (never one instance)."""
    return [*_PHASE1, *FAMILIES]


def spec_task(name: str) -> Task:
    """The task whose spec and architecture the agent is shown for a generation target. A family is
    represented by its instance 0: its spec and shapes are identical across instances (tested)."""
    return get_task(family_instances(name)[0] if name in FAMILIES else name)


__all__ = ["Task", "get_task", "task_names", "family_instances", "generation_targets", "spec_task",
           "FAMILIES", "SparseParity", "Ring2D", "GridNav", "Digits8x8", "ParityHidden", "RingHidden",
           "GridNavHidden"]
