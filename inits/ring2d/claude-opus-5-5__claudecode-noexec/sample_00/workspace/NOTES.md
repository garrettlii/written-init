# Ring classifier

- **Layer 1 (32 units):** approximates each coordinate's square as a piecewise-linear function. For d in {0,1}, sign ±, and j=0..7, a unit computes relu(±x_d − j/8). Weighting these by h=1/8 (when j=0) or 2h (when j≥1) gives the linear interpolant of x_d² on the knots k/8. Its maximum error is h²/4 ≈ 0.004.
- **Layer 2 (4 units used):** each unit reads s_hat = Σ coef·h1 ≈ x0²+x1². The thresholds are 0.16 and 0.5625, each shifted by the mean interpolation bias 2·h²/6 to compensate. The units are relu(s−a+e/2), relu(s−a−e/2), relu(s−b+e/2) and relu(s−b−e/2), with e=0.001.
- **Output:** logit1 = (u1 − u2 − u3 + u4)/e is a trapezoid. It equals 1 for a ≤ s ≤ b and 0 outside, with ramps of width e. logit0 = 0.5. So the network predicts class 1 exactly when 0.4 ≤ r ≤ 0.75, apart from the small error of approximating r².
