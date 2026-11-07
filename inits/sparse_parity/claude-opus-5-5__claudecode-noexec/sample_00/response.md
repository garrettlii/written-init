# Parity of x[1], x[5], x[9], x[14]

The label depends only on s = x[1]+x[5]+x[9]+x[14], which is a whole number from 0 to 4.

- **Layer 1:** Units 0–4 compute u_k = relu(s − k) for k = 0..4. All other units are zero.
- **Layer 2:** Unit 0 computes f = u0 − 2u1 + 2u2 − 2u3 + 2u4. This is a piecewise-linear
  "zigzag" that equals 0, 1, 0, 1, 0 at s = 0, 1, 2, 3, 4, so f = parity(s). Because f ≥ 0,
  the ReLU leaves it unchanged.
- **Output:** logits = [0.5 − f, f − 0.5]. The argmax is class 1 exactly when f = 1.

On paper the network is exact for all 2^16 inputs. Every value it computes is a small
integer or a half-integer, so floating-point rounding is not a concern.
