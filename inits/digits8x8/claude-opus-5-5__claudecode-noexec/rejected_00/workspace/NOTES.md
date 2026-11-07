# Nearest-prototype digit classifier (hand-written weights)

**Algorithm:** I drew 2–4 prototype 8x8 images for each digit by hand in `build.py`, based on how typical
`load_digits` samples look. The network predicts the class whose closest prototype is nearest to the input.
Distance is squared Euclidean distance after a mild 3x3 blur B, which makes the match more tolerant of small shifts:

score_T(x) = |Bx|² − |Bx − BT|² = x·(2BᵀBT) − TᵀBᵀBT

This score is linear in x. The |Bx|² term is the same for every class, so taking the largest score is the same as
taking the smallest distance.

**Layer 1 (64 → 64, 40 units used):** Each class gets 4 prototype slots a, b, c, d. If a class has fewer
prototypes, some are repeated. The units compute:
- `s_a + C`
- `relu(s_b − s_a)`
- `s_c + C`
- `relu(s_d − s_c)`

C = 100 keeps the first and third units positive, so the ReLU leaves them unchanged (|score| ≤ 64).

**Layer 2 (64 → 32, 20 units used):** With M1 = max(s_a, s_b) and M2 = max(s_c, s_d), the units compute:
- `M1 + C = (s_a + C) + relu(s_b − s_a)`
- `relu(M2 − M1)`

**Output (32 → 10):** logit_k is the sum of the two units for class k, which equals
max(s_a, s_b, s_c, s_d) + C. This is exactly the best prototype score for that class, and argmax picks the
nearest prototype's class.
