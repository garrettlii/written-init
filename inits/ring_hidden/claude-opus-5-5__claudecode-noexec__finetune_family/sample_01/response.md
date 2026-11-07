# Ring classifier: construction

**Algorithm:** estimate the radius r = ||x||, then compute a piecewise-linear function f(r) that is positive inside [r_in, r_out] and negative outside it. The logits are ±f/2.

- **Layer 1 (32 units):** I use 16 directions u_k at angles kπ/16, each with a +u_k and a −u_k ReLU. Their sum is Σ|u_k·x|, which equals (2·16/π)·r with under 0.25% angular ripple. So it is a rotation-invariant radius estimate.
- **Layer 2 (32 units):** every unit computes the radius estimate r̂ = (π/32)·Σh1 and outputs a hinge relu(r̂ − t_j). Together the 32 hinges form a linear-spline basis in r.
  - Four knots sit at r_in±0.05 and r_out±0.05.
  - The other 28 are spread evenly over [0.05, 1.0].
- **Output:** I use only the four special hinges plus a bias to build a trapezoid in r. It is −3 outside the ring, rises linearly to +3 inside, and crosses zero exactly at r_in and r_out.
  - Logit1 = f/2 and logit0 = −f/2.
  - The 28 unused hinges have zero output weight. Fine-tuning can use them to reshape f.

**Why this starting point is good for fine-tuning:**
- The labels depend only on r, and the network already outputs a clean spline basis in r.
- Fine-tuning becomes close to logistic regression on that basis.
- Moving a ring edge only needs a shift of the layer-2 biases of the special hinges, which receive direct gradient. With few examples, that is a one-parameter-per-edge adjustment.
- No unit is dead: every knot is at most 1.0, and r can reach √2.

**Assumptions about what I was not told:**
- I picked default radii r_in = 0.40 and r_out = 0.75. This puts about 32% of the points inside the ring, roughly the middle of the allowed 20–50% range and the allowed radii. The untrained network is exact only for that instance.
- For other instances, I assume fine-tuning mainly has to move the two edges.
- I assume the ring is centred exactly at the origin and the labels have no noise.
