# Ring classifier: construction

**Algorithm:** compute the radius r, expand it in a basis of hinge functions of r, and read out a trapezoid in r that is positive inside the ring.

- **Layer 1 (radius):** 16 unit directions u_k = (cos(πk/16), sin(πk/16)), each used as a pair of ReLUs, relu(u_k·x) and relu(−u_k·x), with zero bias. Their sum is Σ_k |u_k·x| = r·Σ_k |cos(φ−θ_k)| ≈ r·16·2/π. Because the directions are evenly spaced, the first harmonic that does not cancel is cos(32φ), so the relative error is about 0.2%.
- **Layer 2 (hinge basis in r):** every unit reads r̂ = (π/32)·Σh1 and outputs h2_j = 30·relu(r̂ − t_j), with thresholds t_j = 0.07 + 0.03j (from 0.07 to 1.00). A linear readout of these units can form any piecewise-linear function of r with breakpoints 0.03 apart. Points with r > 1 are never in the ring.
- **Output:** logit1 − logit0 = −4 + 8.9·[h_9 − h_10 − h_22 + h_23]. This trapezoid is +4 for 0.37 ≲ r ≲ 0.73 (transitions near r_in ≈ 0.355 and r_out ≈ 0.745) and −4 everywhere else, including r > 1.

**Why this suits fine-tuning:** moving the ring to new radii only changes which W2 entries are nonzero. Training W2 is logistic regression on fixed, well-conditioned features, which is convex and needs few examples. The gain of 30 keeps the needed W2 coefficients at about 10, so Adam can reach them within the step budget. The margin of 4 is small enough to retrain quickly.

**Assumptions about what I wasn't told:**
- The radii can be anywhere within the stated limits. As the default with no fine-tuning, I picked a ring in the middle of the allowed range (about 34% of points inside, within the stated 20–50%).
- Breakpoints 0.03 apart are fine enough. The ring is at least 0.15 wide, so it always spans at least 5 hinges.
- Labels follow the ring exactly, with no noise.
