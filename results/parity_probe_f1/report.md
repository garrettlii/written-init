# Parity gradient probe (F1c): claude-opus-5-5__claudecode-noexec__finetune_family

D(S) = dL/dW0 with the true labels minus with soft labels (0.5, 0.5), exact over all 2^16 inputs at the written init (docs/PHASE2_PLAN.md Amendments, F1c).

**(a) share of ||D(S)||^2 on S's 4 rows of W0 (even spread 0.250)**

| sample | parity_hidden_i0 | parity_hidden_i1 | parity_hidden_i2 | parity_hidden_i3 | parity_hidden_i4 | parity_hidden_i5 |
|---|---|---|---|---|---|---|
| sample_00 | 0.911 | 0.893 | 0.911 | 0.911 | 0.886 | 0.886 |
| sample_01 | 0.998 | 0.998 | 0.998 | 0.998 | 0.998 | 0.998 |
| sample_02 | 1.000 | 1.000 | 1.000 | 1.000 | 0.600 | 1.000 |

**(b) ||D(S)|| / ||dL/dW0||**

| sample | parity_hidden_i0 | parity_hidden_i1 | parity_hidden_i2 | parity_hidden_i3 | parity_hidden_i4 | parity_hidden_i5 |
|---|---|---|---|---|---|---|
| sample_00 | 0.287 | 0.329 | 0.287 | 0.287 | 0.364 | 0.364 |
| sample_01 | 0.982 | 0.982 | 0.982 | 0.982 | 0.982 | 0.982 |
| sample_02 | 0.399 | 0.54 | 0.635 | 0.54 | 0.82 | 0.54 |

**(c) rank of S among the 1,820 four-bit subsets by D(S)'s energy (1 = most; ties count against S)**

| sample | parity_hidden_i0 | parity_hidden_i1 | parity_hidden_i2 | parity_hidden_i3 | parity_hidden_i4 | parity_hidden_i5 |
|---|---|---|---|---|---|---|
| sample_00 | 1 | 1 | 1 | 1 | 1 | 1 |
| sample_01 | 1 | 1 | 1 | 1 | 1 | 1 |
| sample_02 | 455 | 91 | 91 | 91 | 15 | 455 |
