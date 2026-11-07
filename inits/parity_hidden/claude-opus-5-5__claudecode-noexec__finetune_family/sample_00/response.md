# Learnable-parity initialisation

## Idea
Parity on a subset S is `cos(pi * s)` with `s = sum_{i in S} x_i`. So the network computes
`f(x) = sum_h T(s_h)`, where `s_h = g_h . x` is a soft selection sum and `T` is a periodic wave
(+1 at even s, -1 at odd s). Fine-tuning only has to move each `g` toward the indicator of S.

Why gradient descent can find S: for `g` with fractional entries, writing
`s - 2 = sum g_i (x_i - 1/2)` gives
`E[Y cos(pi(s-2))] = prod_{i in S} sin(pi g_i/2) * prod_{i not in S} cos(pi g_i/2)`. This is nonzero
for **every** 4-subset, and its gradient increases `g_i` on relevant bits and decreases it on
distractors. A plain ReLU net at a random init has essentially no 4th-order signal.

## Layers
- **Layer 1 (6 used units):** head h gives `h1 = (g_h . x + 1)/4`. Bits are split into blocks
  A={0-3}, B={4-7}, C={8-11}, D={12-15}. Each head puts weight 0.36 on one pair of blocks
  (AB, AC, AD, BC, BD, CD) and 0.14 on the other 8 bits. The weights sum to 4, so the wave is
  centred at s=2, which is the same phase as the final solution (g=1 on S, 0 elsewhere).
  Every S has at least 2 relevant bits, usually 3–4, in some head's focus. That gives a gradient
  signal about 2.5x stronger than a uniform `g` (roughly 6x fewer samples) in most cases, and
  never weaker. The bias keeps the unit active for s >= -1. The weights are stored as g/4, with
  the 4 put back in W1, so `g` moves about 4x faster under Adam than the wave shape does.
- **Layer 2 (60 used units):** for each head, 10 units `0.5*relu(s - k)` with kinks at
  k = 0.25, 0.75, …, 4.75.
- **Output:** slopes ±4 build a trapezoid wave: flat +1 near even s, flat −1 near odd s, valid
  for s ≤ 4.75. The constant term goes in b2. `logit1 - logit0 = -0.3 * sum_h T(s_h)`.
  - The kinks sit at quarter-integers, and the initial s values (multiples of 0.02 that never
    equal a kink) never land exactly on one. That avoids biased relu'(0) gradients.
  - The flat tops copy cos at the integers, where the gradient is zero.
  - All slopes have equal magnitude, so Adam's sign-like shrinking of an uncorrelated wave keeps
    its shape.
- Unused units are zero.

Untrained, the network is at chance (~50%): no fixed starting point can know S. The design aims
for fine-tuning to find S with as few examples as possible. After convergence, the head's flat
regions at integer s give exact parity with a margin.

## Assumptions about what was not given
- S is a uniformly random 4-subset of the 16 bits, and labels are noise-free.
  Label 1 = odd parity of x restricted to S.
- Inputs are uniform i.i.d. bits, as stated, so `E[x_i] = 1/2` (used to centre the wave phase).
- Standard PyTorch-style ReLU with relu'(0)=0, and float32 or float64 arithmetic.
- No particular early-stopping patience. With a small output scale the loss stays near ln 2
  early on, and accuracy rises gradually as `g` aligns.
