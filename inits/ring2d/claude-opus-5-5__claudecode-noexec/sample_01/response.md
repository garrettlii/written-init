# Ring classifier construction

Idea: compute s ≈ r² = x0² + x1², then test 0.16 ≤ s ≤ 0.5625.

**Layer 1 (32 units):** for each coordinate i, sign σ∈{+,−} and knot t_j = j·0.75/8 (j=0..7),
unit = relu(σ·x_i − t_j). Since relu(x−t)+relu(−x−t) = relu(|x|−t) for t ≥ 0, a weighted sum
Σ_j c_j relu(|x_i|−t_j) with c_0 = h, c_j = 2h gives the piecewise-linear interpolant of x_i² at the
knots (exact at knots, overestimate ≤ h²/4; beyond 0.75 it extends linearly, which is fine because
then r > 0.75 anyway).

**Layer 2 (2 units used):** s = Σ c_j·h1 − h²/4 (offset centres the interpolation error to ±h²/4 ≈ ±0.0022).
A = relu(s − m), B = relu(m − s), with m = (0.16+0.5625)/2, so A + B = |s − m|.

**Output:** logit1 − logit0 = 100·(w − A − B), w = (0.5625−0.16)/2; positive exactly when s is in the band.
Expected error is only a thin sliver near the two circles (~0.3% of points).
