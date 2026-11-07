You are an expert in the mechanics of neural networks. Your job is to write the exact weights of a small neural network by reasoning about the computation it should perform, the way a programmer writes a function. You will not train the network, and you have no data. Think through the algorithm first, then translate it into weights layer by layer.

Your job: write the weights of a neural network that solves the task below. Everything you need is in this message.

## Task
Input: a point (x[0], x[1]) drawn uniformly from the square [-1, 1] x [-1, 1].
Label: 1 if the point lies inside a ring centered at the origin, r_in <= sqrt(x[0]^2 + x[1]^2) <= r_out, else 0. The radii r_in and r_out are not given to you. They are fixed within an instance of the task and differ between instances. You can rely on: 0.10 <= r_in < r_out <= 0.95, r_out - r_in >= 0.15, and between 20% and 50% of points lie inside the ring.
Classes: 0 = outside the ring, 1 = inside the ring.

## Architecture (fixed; you cannot change it)
Layer sizes: [2, 32, 32, 2] (1,218 parameters total).
Forward pass (x is a row vector of length 2; weights are stored as (fan_in, fan_out)):
    h0 = x
    h1 = relu(h0 @ W0 + b0)
    h2 = relu(h1 @ W1 + b1)
    logits = h2 @ W2 + b2
    prediction = argmax(logits)
relu(z) = max(z, 0), applied elementwise.
Parameters you must return (name: shape):
    W0: (2, 32)
    b0: (32,)
    W1: (32, 32)
    b1: (32,)
    W2: (32, 2)
    b2: (2,)

## Goal
This network will not be used as written. For each instance of the task, a copy of it will be fine-tuned on a small labeled dataset from that instance (from 16 to about 4,000 examples) and then tested on fresh examples from the same instance; it is also tested with no fine-tuning at all. Fine-tuning minimizes mean cross-entropy with AdamW, batch size 64, for up to 3000 steps, with the learning rate chosen from {0.0001, 0.0003, 0.001, 0.003, 0.01} and the weight decay from {0.0, 0.1} by accuracy on a held-out validation set (ties broken by validation loss). Training stops early when validation stops improving, and the untrained network is also a candidate. Make it the starting point that reaches the highest test accuracy from the fewest examples, for whichever instance it is fine-tuned on. In NOTES.md, also say what you assumed about the parts of the task you were not told.

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