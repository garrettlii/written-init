You are an expert in the mechanics of neural networks. Your job is to write the exact weights of a small neural network by reasoning about the computation it should perform, the way a programmer writes a function. You will not train the network, and you have no data. Think through the algorithm first, then translate it into weights layer by layer.

Your job: write the weights of a neural network that solves the task below. Everything you need is in this message.

## Task
A 9x9 grid with rows r = 0..8 (row 0 at the top, rows increase downward) and columns c = 0..8 (column 0 at the left).
Input: a vector x of length 162. x[0:81] is a one-hot encoding of the agent's cell, with the agent at (r, c) setting x[r*9 + c] = 1. x[81:162] is a one-hot encoding of the goal's cell, with the goal at (r, c) setting x[81 + r*9 + c] = 1. Agent and goal positions are independent and uniform over the grid; they can coincide.
Label: the action of a scripted expert. Let dr = goal_row - agent_row and dc = goal_col - agent_col.
  - if dr == 0 and dc == 0: action 0 (stay)
  - else if |dc| >= |dr|: move horizontally toward the goal: action 4 (right) if dc > 0, action 3 (left) if dc < 0
  - else: move vertically toward the goal: action 2 (down) if dr > 0, action 1 (up) if dr < 0
Classes: 0 = stay, 1 = up, 2 = down, 3 = left, 4 = right.

## Architecture (fixed; you cannot change it)
Layer sizes: [162, 64, 64, 5] (14,917 parameters total).
Forward pass (x is a row vector of length 162; weights are stored as (fan_in, fan_out)):
    h0 = x
    h1 = relu(h0 @ W0 + b0)
    h2 = relu(h1 @ W1 + b1)
    logits = h2 @ W2 + b2
    prediction = argmax(logits)
relu(z) = max(z, 0), applied elementwise.
Parameters you must return (name: shape):
    W0: (162, 64)
    b0: (64,)
    W1: (64, 64)
    b1: (64,)
    W2: (64, 5)
    b2: (5,)

## Goal
Make the network, exactly as you write it, achieve the highest possible accuracy on inputs drawn from the distribution described above. It will be evaluated with no further training.

## What you can use in this session
You can read and edit files in this folder. You cannot run commands or code in this session, so reason the construction through carefully before writing it.

## Deliverable
Write your complete solution to `build.py` in this folder (it contains a stub to replace). Also write `NOTES.md` with a short explanation of the algorithm your network implements and how each layer computes it. When you are done, reply with a one-line summary.

## Rules
- `build_weights()` returns a dict mapping each parameter name above to a numpy array of exactly the listed shape.
- The code may import only `numpy` (as `np`), `math`, `itertools` and `functools`.
- Write the weights directly from your reasoning about the algorithm. Do not generate or enumerate labeled examples to set weights; do not fit, optimize, regress, search over or solve for weights; do not use randomness. The script must be deterministic.
- Do not look for or use any files, datasets, packages or web pages outside this folder.
- Every parameter must be set. Zeros are fine for units you do not use.
- `build_weights()` must finish in under 60 seconds on a laptop CPU.