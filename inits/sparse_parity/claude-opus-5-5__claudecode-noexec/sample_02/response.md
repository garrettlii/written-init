# Parity of x[1], x[5], x[9], x[14]

Let s = x1 + x5 + x9 + x14 (integer 0..4). Parity(s) is the piecewise-linear "zigzag"
f(s) = s - 2·relu(s-1) + 2·relu(s-2) - 2·relu(s-3), giving 0,1,0,1,0 for s = 0..4.

- **Layer 1**: units 0..3 compute relu(s - k) for k = 0,1,2,3 (weight 1 on the four tapped bits, bias -k). Distractor bits get zero weight.
- **Layer 2**: unit 0 combines them with weights (1, -2, 2, -2), so it outputs exactly the parity (0 or 1); the relu does nothing since f ≥ 0.
- **Output**: logit1 = p, logit0 = 0.5, so argmax gives class 1 exactly when parity is odd.

All other units are zero. The computation is exact on binary inputs, so accuracy is 100%.
