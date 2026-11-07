# Design notes

## Idea
A fixed network can't know which 4 bits S are relevant (every fixed function gets about 50% when averaged over
instances), so the weights are built to make **gradient fine-tuning find S fast**.

Parity of S is a function of one linear projection: with a mask m = 1_S, v = m·x = popcount(x_S) and the label is
odd iff cos(πv) = -1. So the network computes `g(v) ≈ cos(πv)` for a *learnable mask* m. In the population,
E[(-1)^{label} cos(π m·x)] = cos(Σφ_i/2) · Π_{i∈S} sin(φ_i/2) · Π_{i∉S} cos(φ_i/2), with φ_i = π m_i.
If the phase term is held at 0 (Σ m_i = 4), ascending this objective pushes m_i up on S and down elsewhere,
with no bad stationary points along the way. The final optimum m = 1_S is exact parity.

A symmetric start (every m_i = 1/4) gives a very weak signal (correlation ≈ 0.008). Smaller masks give much stronger
signals, so I use **8 blocks**, each with mask 0.5 on an 8-bit half-space. Writing bit indices as vectors in F_2^4,
block (k,s) covers the bits whose index has bit k = s. Its correlation with χ_S is 1/16 when the block contains all
of S. When it contains 3 of the 4, the gradient on the missing bit is about 0.1 and the gradient on every other bit
is zero to first order. Of the 1820 possible S, all but 52 (≈97%) have at least 3 bits inside some block.

## Layers
- **Layer 1** (units 0–7, the rest are zero/unused): u_b = relu(1 + 0.5·Σ_{i∈A_b} x_i). This is one shared mask
  unit per block, so the mask gets the exact "shared mask" gradient. The offset 1 keeps it active if weights drift
  negative.
- **Layer 2** (8 hinge units per block, 64 in total): relu(u_b − 1 − κ_j) with knots κ = 0.25, 0.75, …, 3.75.
  The slope changes are ±4, giving a trapezoid wave g_b(v) with period 2 and plateaus +1 at v = 0, 2, 4 and
  −1 at v = 1, 3. The knots sit midway between the lattice points, so:
  - on the initial grid (v ∈ 0.5ℤ), g_b equals cos(πv) and its derivative is ∝ −sin(πv), as the analysis assumes;
  - at the target (v = popcount of S) every input lies on a plateau. The output is exact parity there and the
    mask gradient is zero, so the solution is stable.
- **Output**: logit1 − logit0 = −0.3·Σ_b g_b (split symmetrically, with the constant in b2). Initial p stays near 0.5.
  During fine-tuning, W2 learns to amplify the block that locks onto S and to suppress the others.

## Assumptions about what was not specified
- S is a uniformly random 4-subset, bits are i.i.d. uniform, and labels are noise-free.
- Fine-tuning updates all parameters with a PyTorch-style ReLU (relu'(0) = 0). The unused zero units stay dead,
  and no input or knot lies exactly on a hinge at the start.
- With very few examples (tens), no gradient method can pick S out of 1820 candidates. The design targets the
  hundreds-to-thousands range, where the stronger block signals matter. Without fine-tuning, accuracy is about 50%,
  as it must be for any fixed network.
