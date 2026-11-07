# Starting point for 4-sparse parity on 16 bits

## Idea
Write z_i = 1 - 2x_i (±1). The parity of the relevant set S equals f(Σ_{i∈S} z_i), where
f(u) = (u⁴ − 16u² + 24)/24 is the quartic with f(0)=f(±4)=+1 and f(±2)=−1.
So the network computes **f(t), where t = Σ_i a_i z_i + δ**. That is one learnable
projection followed by a fixed 1-D shape. The task is then solved by a = 1_S, δ = 0.

The subset is unknown, so by symmetry every a_i starts at the same value a0. I picked
**a0 = √(2/11)** because then f(a0·Σz) = (4/121)·e₄(z) + const exactly, i.e. the
initial network is a uniform sum of all 1820 four-bit parities. With this choice:
- ∂f/∂a_i = z_i f'(t) ∝ z_i(6e₃ + 2e₁). Its correlation with χ_S is a0³ > 0 when
  i ∈ S and exactly 0 when i ∉ S. So the very first gradients push only the 4
  relevant weights up. The signal-to-noise ratio is about 0.042 per example, close to
  the symmetry bound of ≈0.047.
- The terms of the gradient that depend only on the network's own output
  (gradients of b0, the bias that sets δ, and of b2) are zero at init by symmetry.
- As the relevant a_i grow, the correlation grows, the output scale grows, and the
  "shrink the junk" part of the loss then drives the irrelevant a_i and δ to 0.

## Layers
- **Layer 1:** a single linear bottleneck unit p = (t + C)/κ, with κ = 32 and C = 8 so
  that p > 0 and the ReLU is the identity. W0[i,0] = −2a0/κ, and b0 = (16a0 + C)/κ.
  The weights are small (about 0.027), so under Adam the a_i (a_i = −κW0/2) move
  about 16·lr per step. They are the fast parameters. The other 63 units are dead
  (weight 0, bias −1), so they get zero gradient.
- **Layer 2:** 24 hinge units relu(±m(t − τ)), with knots at ±0.25, ±0.75, …, ±5.75 and
  m = 0.3. Together they form an even piecewise-linear interpolant of f, built
  outward from the centre, so errors don't accumulate across the range. The
  interpolant is close enough at the target points: f_PL(0)≈0.96, f_PL(±2)≈−0.98,
  f_PL(±4)≈1.21. The other 40 units are dead.
- **Output:** logit1 − logit0 = −β(f_PL(t) − μ), where β = 0.08 and μ is the analytic
  mean of f_PL at init (so initial predictions are balanced). β is kept small
  because the loss term that only depends on the network's output (it pushes all
  a_i to shrink together) scales like β², while the useful signal scales like β.
  The shape weights (|W1| = 9.6, |b1| ≈ 0.7–4.1, |W2| ≈ 0.015–1.0) are large compared with
  Adam's per-step moves at lr ≤ 3e-4, so the shape of f stays mostly intact while
  the a_i move. I expect the lr search to land at 1e-4 or 3e-4.

Untrained accuracy is about 50% for any instance (no fixed function can do better on
average). I expect learning to need several hundred to a few thousand examples. Gradient
methods need on the order of C(16,4) samples for this problem, and the design tries to
get close to that limit, not to beat it.

## Assumptions about unstated details
- Inputs are exactly {0,1}, and class 1 means an odd number of ones among the 4 relevant bits.
- The relevant 4-set is uniform over all C(16,4) sets. Nothing favours particular indices,
  so the init is fully permutation-symmetric.
- Fine-tuning is PyTorch-style AdamW (β1 = 0.9, β2 = 0.999, eps = 1e-8) applied to all
  parameters, including biases, and relu'(0) = 0. The knots are placed so that inputs
  don't land on them at init.
- Early stopping has enough patience to get past an initial plateau of a few hundred
  steps.
