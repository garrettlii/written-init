{system}

Your job: write the weights of a neural network that solves the task below. Everything you need is in this message.

## Task
{task_spec}

## Architecture (fixed; you cannot change it)
{arch_spec}

## Goal
{objective}

## What you can use in this session
{tools}

## Deliverable
{deliverable}

## Rules
- `build_weights()` returns a dict mapping each parameter name above to a numpy array of exactly the listed shape.
- The code may import only `numpy` (as `np`), `math`, `itertools` and `functools`.
- Write the weights directly from your reasoning about the algorithm. Do not generate or enumerate labeled examples to set weights; do not fit, optimize, regress, search over or solve for weights; do not use randomness. The script must be deterministic.
- Do not look for or use any files, datasets, packages or web pages outside this folder.
- Every parameter must be set. Zeros are fine for units you do not use.
- `build_weights()` must finish in under 60 seconds on a laptop CPU.
