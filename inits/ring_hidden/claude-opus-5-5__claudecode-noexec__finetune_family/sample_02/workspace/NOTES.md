# Ring classifier: hand-written weights

## Algorithm
The label depends only on the radius r = |x|. The network works out r, expands it into a
basis of radial hinge functions, and outputs a trapezoidal "bump" in r that is positive
inside the ring.

- **Layer 1 (2→32):** h1_k = relu(cos θ_k·x0 + sin θ_k·x1), with θ_k = 2πk/32. Summed over
  32 evenly spaced directions, Σ_k max(cos(φ−θ_k), 0) ≈ 32/π for any angle φ
  (ripple about 0.1%). So (π/32)·Σ h1_k ≈ r.
- **Layer 2 (32→32):** h2_j = relu(r − t_j), with thresholds t_j = 0.035·j (0 … 1.085).
  W1 = π/32 everywhere and b1 = −t_j. Any piecewise-linear function of r with knots on
  this grid is a linear readout of h2.
- **Output (32→2):** f(r) = logit1 − logit0 = −4 + (8/d)[h2_10 − h2_12 − h2_21 + h2_23],
  where d = 0.07. The result is −4 outside, rising to +4 between r ≈ 0.35 and 0.42, and
  falling back to −4 between r ≈ 0.735 and 0.805. The weights are split symmetrically:
  W2[:,1] = +coef/2, W2[:,0] = −coef/2, b2 = (2, −2).

## Why this suits fine-tuning
- When the network is used without fine-tuning, it classifies a default ring.
- Fine-tuning only has to move the ring edges, and it has two easy ways to do that:
  - shift hinge biases b1 (these are thresholds measured directly in radius units);
  - reweight the 32 hinge readouts in W2, which form a complete linear-spline basis in r.
- No units are dead at initialisation, and the margin of ±4 keeps the gradients on
  misclassified points informative.

## Assumptions about the unknowns
- The default ring is r_in ≈ 0.385 and r_out ≈ 0.77. That covers about 35% of the square,
  which is mid-range for the allowed 20–50%, and the radii sit near the middle of the
  allowed range of r_in and r_out.
- I assumed that no ring boundary goes beyond about 1.0 in radius, since r_out ≤ 0.95.
  The hinge grid covers 0 to 1.085, at a resolution of 0.035.
- I assumed the ring stays centred at the origin and that only the radii change between
  instances.
