# Parity gradient probe with baselines (F1c extension): claude-opus-5-5__claudecode-noexec__finetune_family

D(S) = dL/dW0 with the true labels minus with soft labels (0.5, 0.5), exact over all 2^16 inputs at initialization (docs/PHASE2_PLAN.md Amendments, F1c and its extension). (a) share of ||D(S)||^2 on S's 4 rows of W0 (even spread 0.250); (b) ||D(S)|| / ||dL/dW0||; (c) rank of S among the 1,820 four-bit subsets by D(S)'s energy on their rows (1 = most; ties count against S); (d) ||D(S)||.

## Written samples

**(a) share**

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

**(c) rank of 1,820**

| sample | parity_hidden_i0 | parity_hidden_i1 | parity_hidden_i2 | parity_hidden_i3 | parity_hidden_i4 | parity_hidden_i5 |
|---|---|---|---|---|---|---|
| sample_00 | 1 | 1 | 1 | 1 | 1 | 1 |
| sample_01 | 1 | 1 | 1 | 1 | 1 | 1 |
| sample_02 | 455 | 91 | 91 | 91 | 15 | 455 |

**(d) ||D(S)||**

| sample | parity_hidden_i0 | parity_hidden_i1 | parity_hidden_i2 | parity_hidden_i3 | parity_hidden_i4 | parity_hidden_i5 |
|---|---|---|---|---|---|---|
| sample_00 | 0.114 | 0.138 | 0.114 | 0.114 | 0.158 | 0.158 |
| sample_01 | 0.107 | 0.107 | 0.107 | 0.107 | 0.107 | 0.107 |
| sample_02 | 0.0188 | 0.0265 | 0.0325 | 0.0265 | 0.0593 | 0.0265 |

## Baselines

Random He init: seeds 0-19. norm_matched and shuffled_noise: seeds 0-5 of each written sample. (a)-(c) over the inits with label signal, as mean (min-max) or median (min-max); (d) over all inits.

| init | sample | instance | inits | no label signal | (a) share | (b) ratio | (c) rank, median (min-max) | (d) ||D(S)|| |
|---|---|---|---|---|---|---|---|---|
| random | - | parity_hidden_i0 | 20 | 0 | 0.624 (0.535-0.730) | 0.0253 (0.00744-0.0778) | 1 (1-2) | 0.00794 (0.0053-0.0112) |
| norm_matched | sample_00 | parity_hidden_i0 | 6 | 0 | 0.605 (0.416-0.726) | 0.00632 (0.0028-0.0146) | 2 (1-37) | 0.0476 (0.0351-0.0633) |
| shuffled_noise | sample_00 | parity_hidden_i0 | 6 | 0 | 0.469 (0.214-0.815) | 0.00409 (0.00207-0.00872) | 70 (3-1388) | 0.022 (0.0094-0.0495) |
| norm_matched | sample_01 | parity_hidden_i0 | 6 | 0 | 0.513 (0.197-0.806) | 0.000547 (1.96e-05-0.00268) | 233 (1-1076) | 0.00405 (0.000189-0.0188) |
| shuffled_noise | sample_01 | parity_hidden_i0 | 6 | 6 | - | - | - | 4.99e-17 (9.69e-18-2.02e-16) |
| norm_matched | sample_02 | parity_hidden_i0 | 6 | 0 | 0.628 (0.532-0.731) | 0.0122 (0.00307-0.0393) | 2 (1-46) | 0.0136 (0.0101-0.0155) |
| shuffled_noise | sample_02 | parity_hidden_i0 | 6 | 0 | 0.635 (0.452-0.798) | 0.00187 (0.000952-0.00272) | 36 (2-146) | 0.00198 (0.000835-0.00373) |
| random | - | parity_hidden_i1 | 20 | 0 | 0.619 (0.474-0.771) | 0.0309 (0.00485-0.0779) | 1 (1-2) | 0.00854 (0.00497-0.0119) |
| norm_matched | sample_00 | parity_hidden_i1 | 6 | 0 | 0.692 (0.545-0.837) | 0.00722 (0.00298-0.0168) | 1 (1-15) | 0.0525 (0.0375-0.0627) |
| shuffled_noise | sample_00 | parity_hidden_i1 | 6 | 0 | 0.507 (0.260-0.775) | 0.00299 (0.000979-0.0074) | 56 (3-654) | 0.0192 (0.00308-0.0438) |
| norm_matched | sample_01 | parity_hidden_i1 | 6 | 0 | 0.641 (0.443-0.883) | 0.000487 (5.67e-05-0.00198) | 12 (2-89) | 0.00447 (0.000474-0.0191) |
| shuffled_noise | sample_01 | parity_hidden_i1 | 6 | 6 | - | - | - | 4.59e-17 (9.95e-18-1.75e-16) |
| norm_matched | sample_02 | parity_hidden_i1 | 6 | 0 | 0.710 (0.589-0.851) | 0.0141 (0.00315-0.0477) | 1 (1-17) | 0.0147 (0.0112-0.0186) |
| shuffled_noise | sample_02 | parity_hidden_i1 | 6 | 0 | 0.577 (0.316-0.678) | 0.00135 (0.000419-0.00246) | 34 (1-361) | 0.00129 (0.000359-0.00241) |
| random | - | parity_hidden_i2 | 20 | 0 | 0.600 (0.427-0.745) | 0.0267 (0.00694-0.0594) | 1 (1-2) | 0.00846 (0.00596-0.0109) |
| norm_matched | sample_00 | parity_hidden_i2 | 6 | 0 | 0.507 (0.332-0.845) | 0.00491 (0.00211-0.00692) | 66 (1-156) | 0.0437 (0.0192-0.0689) |
| shuffled_noise | sample_00 | parity_hidden_i2 | 6 | 0 | 0.560 (0.214-0.874) | 0.00262 (0.001-0.00667) | 17 (1-1413) | 0.0153 (0.0051-0.0379) |
| norm_matched | sample_01 | parity_hidden_i2 | 6 | 0 | 0.519 (0.188-0.975) | 0.000258 (1.9e-05-0.00106) | 272 (10-1169) | 0.00196 (0.000159-0.00744) |
| shuffled_noise | sample_01 | parity_hidden_i2 | 6 | 6 | - | - | - | 4.38e-17 (1.01e-17-1.62e-16) |
| norm_matched | sample_02 | parity_hidden_i2 | 6 | 0 | 0.557 (0.345-0.810) | 0.00987 (0.00339-0.0205) | 3 (1-374) | 0.0139 (0.00717-0.0214) |
| shuffled_noise | sample_02 | parity_hidden_i2 | 6 | 0 | 0.703 (0.161-0.899) | 0.00359 (0.000574-0.0107) | 6 (1-1670) | 0.00298 (0.000402-0.00677) |
| random | - | parity_hidden_i3 | 20 | 0 | 0.620 (0.456-0.773) | 0.0251 (0.00821-0.0726) | 1 (1-3) | 0.0084 (0.00442-0.014) |
| norm_matched | sample_00 | parity_hidden_i3 | 6 | 0 | 0.575 (0.266-0.737) | 0.00556 (0.00286-0.0108) | 4 (1-457) | 0.049 (0.0182-0.0913) |
| shuffled_noise | sample_00 | parity_hidden_i3 | 6 | 0 | 0.625 (0.279-0.914) | 0.00279 (0.0019-0.00424) | 2 (1-507) | 0.0154 (0.00839-0.024) |
| norm_matched | sample_01 | parity_hidden_i3 | 6 | 0 | 0.622 (0.257-0.988) | 0.00035 (1.3e-05-0.00135) | 66 (5-861) | 0.00276 (0.000109-0.00951) |
| shuffled_noise | sample_01 | parity_hidden_i3 | 6 | 6 | - | - | - | 4.61e-17 (9.79e-18-1.8e-16) |
| norm_matched | sample_02 | parity_hidden_i3 | 6 | 0 | 0.557 (0.336-0.704) | 0.00865 (0.0035-0.0181) | 11 (1-456) | 0.0136 (0.00536-0.0277) |
| shuffled_noise | sample_02 | parity_hidden_i3 | 6 | 0 | 0.573 (0.250-0.914) | 0.00431 (0.000518-0.0133) | 106 (6-886) | 0.00346 (0.000828-0.00853) |
| random | - | parity_hidden_i4 | 20 | 0 | 0.536 (0.409-0.679) | 0.0296 (0.00812-0.102) | 1 (1-24) | 0.00923 (0.00581-0.0159) |
| norm_matched | sample_00 | parity_hidden_i4 | 6 | 0 | 0.670 (0.547-0.833) | 0.00512 (0.00166-0.00644) | 4 (1-15) | 0.0457 (0.0208-0.0884) |
| shuffled_noise | sample_00 | parity_hidden_i4 | 6 | 0 | 0.586 (0.302-0.880) | 0.00368 (0.00157-0.00763) | 12 (1-440) | 0.0205 (0.00872-0.0433) |
| norm_matched | sample_01 | parity_hidden_i4 | 6 | 0 | 0.626 (0.261-0.936) | 0.000252 (8.33e-06-0.000886) | 56 (1-814) | 0.00195 (8.02e-05-0.00622) |
| shuffled_noise | sample_01 | parity_hidden_i4 | 6 | 6 | - | - | - | 4.88e-17 (1.06e-17-1.95e-16) |
| norm_matched | sample_02 | parity_hidden_i4 | 6 | 0 | 0.601 (0.450-0.718) | 0.00875 (0.00178-0.0183) | 1 (1-14) | 0.0143 (0.00586-0.0298) |
| shuffled_noise | sample_02 | parity_hidden_i4 | 6 | 0 | 0.528 (0.057-0.903) | 0.00697 (0.000629-0.0265) | 83 (2-1820) | 0.00635 (0.00101-0.0259) |
| random | - | parity_hidden_i5 | 20 | 0 | 0.603 (0.467-0.728) | 0.0272 (0.0065-0.0873) | 1 (1-7) | 0.00801 (0.00569-0.0117) |
| norm_matched | sample_00 | parity_hidden_i5 | 6 | 0 | 0.701 (0.572-0.859) | 0.00694 (0.0033-0.0138) | 2 (1-6) | 0.0518 (0.0368-0.0902) |
| shuffled_noise | sample_00 | parity_hidden_i5 | 6 | 0 | 0.585 (0.265-0.756) | 0.0049 (0.000834-0.0142) | 4 (1-703) | 0.0303 (0.00286-0.0843) |
| norm_matched | sample_01 | parity_hidden_i5 | 6 | 0 | 0.659 (0.343-0.980) | 0.00025 (9.06e-05-0.000713) | 46 (1-312) | 0.00231 (0.000758-0.00686) |
| shuffled_noise | sample_01 | parity_hidden_i5 | 6 | 6 | - | - | - | 4.64e-17 (9.97e-18-1.81e-16) |
| norm_matched | sample_02 | parity_hidden_i5 | 6 | 0 | 0.733 (0.599-0.857) | 0.0129 (0.00357-0.0338) | 1 (1-5) | 0.0141 (0.0113-0.0223) |
| shuffled_noise | sample_02 | parity_hidden_i5 | 6 | 0 | 0.658 (0.466-0.856) | 0.00211 (0.000437-0.00431) | 8 (3-90) | 0.00202 (0.000372-0.00422) |

## (c) with every subset as the hidden subset (written samples)

Each of the 1,820 four-bit subsets in turn is the hidden subset. A rank carrying no information about the subset would be spread over 1-1,820 (median about 910).

| sample | subsets with label signal | rank 1 | rank <= 18 (top 1%) | rank <= 91 (top 5%) | rank percentiles 5 / 25 / 50 / 75 / 95 |
|---|---|---|---|---|---|
| sample_00 | 1820 | 1820 | 1820 | 1820 | 1 / 1 / 1 / 1 / 1 |
| sample_01 | 1820 | 1820 | 1820 | 1820 | 1 / 1 / 1 / 1 / 1 |
| sample_02 | 1768 | 40 | 584 | 1416 | 5 / 15 / 91 / 91 / 455 |