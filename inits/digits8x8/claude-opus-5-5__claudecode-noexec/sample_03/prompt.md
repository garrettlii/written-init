You are an expert in the mechanics of neural networks. Your job is to write the exact weights of a small neural network by reasoning about the computation it should perform, the way a programmer writes a function. You will not train the network, and you have no data. Think through the algorithm first, then translate it into weights layer by layer.

Your job: write the weights of a neural network that solves the task below. Everything you need is in this message.

## Task
Input: an 8x8 grayscale image of a handwritten digit, from the UCI 'Optical Recognition of Handwritten Digits' dataset (the version bundled with scikit-learn as load_digits). x has length 64 in row-major order: x[r*8 + c] is the pixel at row r (0 = top) and column c (0 = left). Each value is the original 0-16 count divided by 16, so it lies in [0, 1]; ink (the pen stroke) is HIGH, background is 0. Digits are roughly centered and size-normalized.
Label: the digit shown.
Classes: 0-9, the digit itself.

## Architecture (fixed; you cannot change it)
Layer sizes: [64, 64, 32, 10] (6,570 parameters total).
Forward pass (x is a row vector of length 64; weights are stored as (fan_in, fan_out)):
    h0 = x
    h1 = relu(h0 @ W0 + b0)
    h2 = relu(h1 @ W1 + b1)
    logits = h2 @ W2 + b2
    prediction = argmax(logits)
relu(z) = max(z, 0), applied elementwise.
Parameters you must return (name: shape):
    W0: (64, 64)
    b0: (64,)
    W1: (64, 32)
    b1: (32,)
    W2: (32, 10)
    b2: (10,)

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