# Ring classifier

**What the network computes:** it approximates r² = x0² + x1² and checks whether 0.16 ≤ r² ≤ 0.5625.

- **Layer 1 (32 ReLUs):** for each coordinate and each sign, there are units relu(±x_d − k/8) for k = 0..7. Weighting the k=0 unit by 1/8 and the k≥1 units by 2/8 gives the piecewise-linear interpolant of x_d² at knots spaced 1/8 apart. The interpolant is too high by between 0 and 1/256 per coordinate.
- **Layer 2 (4 ReLUs used):** each unit reads s = Σ c_j h1_j − 1/256. Subtracting 1/256 centres the error at ±1/256 on r². For each threshold t ∈ {0.16, 0.5625} there are two units, relu(1000(s−t)) and relu(1000(s−t) − 1). The first minus the second is a clipped ramp, roughly the step function [s ≥ t].
- **Output:** logit1 = step_low − step_high, which is about 1 inside the ring and 0 outside; logit0 = 0.5. The other units are zero.

The error in r² is at most about ±0.004, so the boundaries move by at most about 0.005 in radius. Accuracy should be about 99% or better.
