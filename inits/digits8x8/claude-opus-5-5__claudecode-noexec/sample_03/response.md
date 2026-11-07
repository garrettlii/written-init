# Nearest-prototype classifier with an exact max over prototypes

**Algorithm.** I drew four 8x8 prototype images by hand for each digit (40 in total), covering common writing styles: a 7 with and without a crossbar, a 4 drawn open or closed, a 1 with and without a base, slanted and upright forms, and so on. Each prototype gets a light blur so its strokes look like the thick, smooth strokes in the downsampled dataset. Each prototype T is scored against the input x with
`s = x·T − ½‖T‖²`.
This equals `−½‖x−T‖²` plus a term that is the same for every class, so a higher score means a closer prototype. The logit for each class is the maximum score among its four prototypes. The predicted digit is therefore the class of the nearest prototype.

**Layer 0 (40 of 64 units used).** For each class, with prototype scores s0..s3:
`u0 = relu(s0 + C)`, `u1 = relu(s1 − s0)`, `u2 = relu(s2 + C)`, `u3 = relu(s3 − s2)`.
Every score is linear in x, so each unit is a single dot product plus a bias. The offset C = 40 is larger than the largest possible ½‖T‖², so u0 and u2 never clip and they pass their score through unchanged. As a result, `u0+u1 = max(s0,s1)+C` and `u2+u3 = max(s2,s3)+C`.

**Layer 1 (20 of 32 units used).** For each class:
`v0 = relu(u0+u1)` (always positive, so it passes through) and `v1 = relu((u2+u3) − (u0+u1))`.

**Output.** `logit_k = v0 + v1 = max(s0..s3) + C`. C is the same for every class, so it does not change the argmax. All unused units have zero weights and zero biases.
