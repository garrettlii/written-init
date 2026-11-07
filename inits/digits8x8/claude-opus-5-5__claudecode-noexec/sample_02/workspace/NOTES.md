# Hand-built digit classifier: max-over-templates correlation

**Algorithm.** Each class has 3–4 hand-drawn 8x8 prototype strokes (for example upright, serif and
slanted 1s, and open and closed 4s). Each prototype is blurred with a 3x3 kernel so it looks
like a thick, averaged stroke. It is then made zero-mean and scaled to unit norm, giving a
filter `w`. The score `<x, w>` equals the Pearson correlation between the image and the
prototype multiplied by `||x - mean(x)||`. That factor is the same for every template, so
the argmax over templates is the argmax of correlation. The predicted class is the one whose
best-matching template scores highest.

**Layer 1 (64 → 40 used).** For class k with filters a, b, c, d (if a class has fewer than
four, some are repeated), four units compute `relu(S(a-b)·x)`, `S·b·x + C`, `relu(S(c-d)·x)`
and `S·d·x + C`, with S = 10 and C = 100. C is larger than any possible |score| (at most 80),
so the units with the offset never clip and act as linear pass-throughs.

**Layer 2 (40 → 20 used).** Since `max(a,b) = b + relu(a-b)`, we have `m1 = max(a,b)+C` and
`m2 = max(c,d)+C`. Two units per class compute `relu(m1 - m2)` and `relu(m2)`; m2 is always
positive.

**Output.** `logit_k = relu(m1-m2) + m2 = max(a,b,c,d) + C`, so the result is the max
template score plus the same offset for every class. The unused units have zero weights.
