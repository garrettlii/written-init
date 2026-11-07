# Finish Phase 1 (digits) and pre-register Phase 2 (partial-spec families)

Written 2026-11-04. This document is a pre-registration: commit it together with the Phase 2 code **before** any Phase 2 sample is generated, and record the commit hash in `docs/DECISIONS.md`. Anything decided after seeing Phase 2 results goes in a dated amendment at the bottom, never as an edit above it.

---

## 0. Where Phase 1 stands (`results/main_v1`)

| task | written init, zero-shot | random init at its largest budget | written init is worth |
|---|---|---|---|
| gridnav | 1.000 | 0.959 at 4,096 | more than 4,096 examples (lower bound) |
| ring2d | 0.999 | 0.985 at 4,096 | more than 4,096 examples (lower bound) |
| sparse_parity | 1.000 | 1.000, reached between 256 and 1,024 | 256 to 1,024 examples |
| digits8x8 (1 sample, provisional) | 0.358 | 0.938 at 256 | at most 16 examples; 1.26x at 16 (CI 1.00-1.86), 0.82x at 256 |

- H3 (structure, not scale) is supported on all four tasks. H5 (noise helps fine-tuning) is not supported.
- Observed, not pre-registered: fine-tuning slightly degrades written inits that are already perfect, and only the low-margin samples (gridnav sample_02/03, ring2d sample_00/02). The high-margin samples are untouched. That's 1-2 seeds per sample, so it's suggestive only.
- **The gap Phase 2 addresses:** three of the four tasks are solved before any training, so "how much data is a written init worth during fine-tuning" was only really tested on digits.

---

## Part A: Finish Phase 1 (digits)

### A.1 Memorization outcome so far
Three digits samples were generated with the `zero_shot` objective. sample_00 reproduced `load_digits` rows 0-8 nearly pixel-exactly, including test-split row 6, and was rejected. sample_01 and sample_02 passed `scripts/memcheck_digits.py` with 0 near-duplicates and were approved.

### A.2 Exclusion rule (applies to all digits samples, past and future)
A digits sample is **excluded** if any prototype it contains, or any W0 column, is closer to a real `load_digits` image (including shifts of up to ±1 pixel) than the dataset's minimum same-class nearest-neighbour distance between real images. Excluded samples are kept on disk as `rejected_XX`. The writeup reports how many samples were generated and how many were excluded.

**Disclosure:** this rule was written after sample_00 was observed. The writeup must say so.

### A.3 Replacement samples
Generate digits samples (same prompt, `zero_shot` objective, `claude` / `noexec`) until three clean samples are approved. Report the total generated and the number excluded (currently 1 of 3).

### A.4 Budget rule for small training pools (also used in Phase 2)
If a budget exceeds a task's training pool, it is replaced by the pool size, and a budget that ends up duplicated is dropped. Job keys record the actual budget used. For digits, 1,024 becomes 1,000 and 4,096 is dropped.

### A.5 Digits rerun
- New config `configs/digits_v1b.yaml`. Same arms, hyperparameter grid and training as `default.yaml`. `tasks: [digits8x8]`, `budgets: [0, 16, 64, 256, 1024]` (so 1,024 becomes 1,000), `seeds: [0, 1, 2, 3, 4, 5]` (2 per sample with 3 samples), `require_audited: true`.
- Run name `main_v1_digits`. The digits rows in `main_v1` stay on disk, but this run supersedes them for reporting (DECISIONS entry).
- Report the other three Phase 1 tasks from `main_v1`, and digits from `main_v1_digits`, saying so explicitly.

---

## Part B: Phase 2, partial-spec families

### B.1 Question
When an agent knows the algorithm family but not the specific instance, how much fine-tuning data does its written initialization save, compared with random initialization?

### B.2 Design in one paragraph
Each **family** has a few hidden parameters: which bits matter, the radii, or the wall layout. The agent is told the family, and that those parameters exist and are hidden, but not their values. It writes **one** initialization per sample for the whole family. That same init is then fine-tuned and tested separately on each of 3 hidden **instances**. Fine-tuning has to discover the instance; the written init can only contribute structure. Phase 1 tasks are the full-information end of the same scale.

### B.3 Families

| family | told to the agent | hidden per instance | architecture | why it's informative |
|---|---|---|---|---|
| `parity_hidden` | parity of exactly 4 of 16 bits | which 4 bits | 16-64-64-2, ReLU (same as sparse_parity) | identifying the subset takes ~11 bits of information (log2 C(16,4) ≈ 10.8), yet random init needed 256-1,024 examples in Phase 1. Does knowing the algorithm help with the search? |
| `ring_hidden` | a ring centered at the origin, with bounds on the radii | the two radii | 2-32-32-2, ReLU (same as ring2d) | structure (computing r²) is the hard part. Only two thresholds remain to learn. |
| `gridnav_hidden` | shortest-path expert on a grid with some walls | the wall layout | 162-64-64-5, ReLU (same as gridnav) | the wall-free rule is a partially correct init: right wherever walls don't change the first move. Fine-tuning has to learn the detours. |

Digits stays as it is: it's naturally partially writable, and is covered in Part A.

### B.4 Exact task specs shown to the agent (use verbatim)

**parity_hidden**
> Input: 16 binary values x[0], ..., x[15], each 0.0 or 1.0, drawn independently and uniformly at random.
> Label: the parity (XOR) of exactly 4 of the 16 bits; the other 12 bits are irrelevant distractors. Which 4 bits is not given to you. It is fixed within an instance of the task, differs between instances, and every set of 4 bits is possible.
> Classes: 0 = even parity, 1 = odd parity.

**ring_hidden**
> Input: a point (x[0], x[1]) drawn uniformly from the square [-1, 1] x [-1, 1].
> Label: 1 if the point lies inside a ring centered at the origin, r_in <= sqrt(x[0]^2 + x[1]^2) <= r_out, else 0. The radii r_in and r_out are not given to you. They are fixed within an instance of the task and differ between instances. You can rely on: 0.10 <= r_in < r_out <= 0.95, r_out - r_in >= 0.15, and between 20% and 50% of points lie inside the ring.
> Classes: 0 = outside the ring, 1 = inside the ring.

**gridnav_hidden**
> A 9x9 grid with rows r = 0..8 (row 0 at the top, rows increase downward) and columns c = 0..8 (column 0 at the left). Some cells are walls: between 8 and 12 of the 81 cells, placed so that all non-wall cells are connected through up, down, left and right moves. Which cells are walls is not given to you. It is fixed within an instance of the task and differs between instances.
> Input: a vector x of length 162. x[0:81] is a one-hot encoding of the agent's cell, with the agent at (r, c) setting x[r*9 + c] = 1. x[81:162] is a one-hot encoding of the goal's cell, with the goal at (r, c) setting x[81 + r*9 + c] = 1. Agent and goal are on non-wall cells, independent and uniform over them; they can coincide.
> Label: the first move of a scripted expert that walks a shortest path from the agent to the goal, one cell up, down, left or right per step, never into a wall or off the grid. Let dr = goal_row - agent_row and dc = goal_col - agent_col.
>   - if dr == 0 and dc == 0: action 0 (stay)
>   - otherwise, among the moves that begin some shortest path, the expert takes the move the wall-free rule would take, if it is one of them. The wall-free rule: if |dc| >= |dr|, right (4) when dc > 0 or left (3) when dc < 0; otherwise down (2) when dr > 0 or up (1) when dr < 0.
>   - if the wall-free move does not begin a shortest path, the expert takes the first of right (4), left (3), down (2), up (1) that does.
> Classes: 0 = stay, 1 = up, 2 = down, 3 = left, 4 = right.

### B.5 Instances (3 per family, blinded)
- Drawn in code (`src/written_init/tasks/hidden.py`) with `rng = numpy.random.default_rng([2026, 11, 4, family_index, i])`, where family_index is parity_hidden = 1, ring_hidden = 2, gridnav_hidden = 3, and i = 0, 1, 2. Rejection sampling until the constraints hold; each rejected draw is replaced by the next draw from the same `rng`:
  - **parity_hidden:** a 4-subset of {0..15}, uniform. Excludes the Phase 1 subset {1, 5, 9, 14}. The three instances are distinct. Draw: `sorted(rng.choice(16, 4, replace=False))`, redrawn if it equals {1, 5, 9, 14} or the subset of an earlier instance (0..i-1).
  - **ring_hidden:** r_in and r_out uniform on [0.10, 0.95] with r_out - r_in >= 0.15 and an inside fraction π(r_out² - r_in²)/4 in [0.20, 0.50]. Draw: `r_in, r_out = rng.uniform(0.10, 0.95, 2)`, both redrawn until 0.10 <= r_in < r_out <= 0.95, r_out - r_in >= 0.15 and the inside fraction is in [0.20, 0.50].
  - **gridnav_hidden:** wall count uniform in {8, ..., 12}, positions uniform, rejected unless the free cells are 4-connected. Draw: `n = rng.integers(8, 13)`, then walls = `rng.choice(81, n, replace=False)` as cell indices r*9 + c, both redrawn until the free cells are 4-connected.
- **Blinding:** instance values exist only in task code and results, never in `prompts/`, `inits/`, or any text an agent sees. This document gives the seeds, not the values. The agent can't read the repository (verified fence). The spec text is identical for every instance of a family.
- **Partitions:**
  - parity_hidden reuses the Phase 1 enumeration and split of all 65,536 inputs (split seed 12345); only the labels change per instance.
  - ring_hidden is continuous, sampled with the existing named streams.
  - gridnav_hidden partitions all (agent, goal) pairs over free cells per instance: 1,500 test, 256 val, the rest train (about 3,000-3,600). The pairs are enumerated in Phase 1 gridnav's order (agent row, agent column, goal row, goal column) and filtered to free cells, then split with seed 12345 as in Phase 1.
- **Task names** in results: `parity_hidden_i0`, `parity_hidden_i1`, `parity_hidden_i2`, and so on. Each instance task has a `family` attribute, and written inits are looked up under `inits/<family>/<source>/`.

### B.6 What the agent is told about fine-tuning (new objective `finetune_family`)
New file `prompts/objectives/finetune_family.md`. Placeholders are filled from `configs/phase2.yaml` at generation time, so the prompt can't drift from the protocol:

> This network will not be used as written. For each instance of the task, a copy of it will be fine-tuned on a small labeled dataset from that instance (from 16 to about 4,000 examples) and then tested on fresh examples from the same instance; it is also tested with no fine-tuning at all. Fine-tuning minimizes mean cross-entropy with {optimizer}, batch size {batch_size}, for up to {max_steps} steps, with the learning rate chosen from {lr_grid} and the weight decay from {wd_grid} by accuracy on a held-out validation set (ties broken by validation loss). Training stops early when validation stops improving, and the untrained network is also a candidate. Make it the starting point that reaches the highest test accuracy from the fewest examples, for whichever instance it is fine-tuned on. In NOTES.md, also say what you assumed about the parts of the task you were not told.

Rendering: `{optimizer}` is the optimizer's display name (`adamw` becomes AdamW), `{batch_size}` and `{max_steps}` are plain integers, and `{lr_grid}` and `{wd_grid}` are the config values as a comma-separated set in braces, e.g. {0.0001, 0.0003, 0.001, 0.003, 0.01}.

The rules in `agent_task.md` are unchanged. With this objective the source folder is `claude-opus-5-5__claudecode-noexec__finetune_family` (generate.py appends the objective), and the config arms must use it.

### B.7 Protocol (unchanged from Phase 1 except where marked)
- Generation: `claude` / `noexec` only. Same fence, isolation check valid for the CLI version in use. 3 samples per family, all audited.
- Arms: random, written, written_noise, shuffled_noise, norm_matched, shuffled (secondary). Same definitions and α = 0.1.
- Budgets: 0, 16, 64, 256, 1,024, 4,096, with the A.4 pool rule (gridnav_hidden's top budget becomes its pool size).
- **Seeds: 0-5 (changed from 5 to 6),** so each of the 3 samples gets exactly 2 seeds per instance.
- Training, hyperparameter grid, validation (256), test (2,000; 1,500 for gridnav_hidden) and selection rule: identical to `default.yaml`.
- `require_audited: true`.

### B.8 Metrics
**Primary:** per family and per instance, the paired difference (written − random) in test accuracy at **budgets 16 and 64**. That's the mean over 6 seeds, paired by seed (same training examples), with a 95% bootstrap CI over seeds.

**Secondary:**
1. Data multiplier per instance using the existing `resolve` rules (chance, ceiling, range, bounds, brackets).
2. Samples-to-target: the budget at which each arm's mean test accuracy reaches 0.95, and separately 0.99, by log-linear interpolation on that arm's own curve, censored outside the measured range. Reported as the random / written ratio per instance. Budget 0 is included: if an arm's zero-shot mean already meets the target, its samples-to-target is 0, and a written value of 0 makes the ratio "not defined (written needs no data)". A target first met between budgets 0 and 16 reads "<= 16".
3. Zero-shot test accuracy per sample and per instance.
4. Structure control (written_noise − shuffled_noise) and scale control (written − norm_matched), paired by seed, per family, pooled over instances (18 instance-seed pairs). The 95% CI comes from a bootstrap stratified by instance: resample seeds within each instance, take each instance's mean, then average the three instances. Each instance keeps equal weight, because instances are not interchangeable. Only budgets measured in every instance are pooled; gridnav_hidden's top budget is its pool size (A.4), which differs per instance, so it is reported per instance only.

**Exploratory, not used for claims:**
- The relation between each sample's zero-shot test loss on an instance and its accuracy after fine-tuning at 16 and 64 examples (follows up the Phase 1 margin observation).
- A classification of the assumptions agents state in NOTES.md, e.g. "equal weights on all bits" or "guessed radii 0.4 / 0.75".

### B.9 Hypotheses

- **H7.** On ring_hidden and gridnav_hidden, written − random > 0 at budget 16 and at budget 64. Supported for a family if the paired CI's lower bound is above 0 in at least 2 of its 3 instances, at both budgets.
- **H8 (open, no direction pre-registered).** On parity_hidden, does knowing the algorithm help when the hard part is finding which inputs matter? Report the primary metric either way.
  - A clear positive result means structural knowledge speeds up gradient descent's search for the relevant subset.
  - A null means structural knowledge doesn't substitute for identifying the relevant inputs, despite the ~11-bit information requirement.
- **H9 (zero-shot predictions, which double as integrity checks).**
  - parity_hidden written zero-shot accuracy is 0.5 within ±0.04 on every instance: an init that doesn't encode the hidden subset is uncorrelated with the label, and ±0.04 is about 3.5 standard errors on 2,000 test points. **A value outside that band is treated as a possible leak and investigated before any other Phase 2 result is read.** The analysis canary line lists the instance mean and each sample's zero-shot accuracy. It flags OUTSIDE if the mean or any single sample is outside [0.46, 0.54], because a leak in one sample could average out. The H9 verdict itself uses the instance mean.
  - gridnav_hidden written zero-shot accuracy is at least 0.75 on every instance, because the wall-free rule is right wherever the walls don't change the first move.
  - ring_hidden: no prediction.
- **H10 (structure).** written_noise − shuffled_noise > 0 at budgets 16, 64 and 256 for each family, pooled over instances (CI lower bound > 0).
- **H11 (exploratory).** Lower zero-shot loss on an instance predicts higher accuracy after fine-tuning at 16 and 64 examples. Reported as a correlation over sample × instance cells, with no claim attached.

### B.10 Integrity additions
- **Tests:**
  - For each family, the spec text is byte-identical across instances and contains no instance value: no subset, no radius to 2 or 3 decimals, no wall index list. The spec's set of decimal numbers must be exactly B.4's. Decimal numbers that are part of the fixed text itself are excluded from the radius check: B.4's bounds 0.10, 0.95 and 0.15, and for a reference init its spec-derived constants. They were fixed before any instance was drawn, so a coincidental match carries no instance information (at 2 decimals this happens for at least one ring instance).
  - Every generated prompt for a family has the same `prompt_hash`.
- **Audits:**
  - The same `/audit-init` checklist applies. A missing NOTES.md assumption statement gets a note in the audit, not a rejection.
  - No memorization check is needed; the data is synthetic.
- **Canary:** H9's parity band is the leak detector. Check it first.
- **CLI version:** before generating, check `claude --version`. If it isn't the version the last passing isolation check ran on, rerun the check.

### B.11 Threats to validity
| threat | mitigation |
|---|---|
| A result driven by one lucky instance, e.g. guessed radii that happen to match | 3 instances, per-instance reporting, the "2 of 3" rule for claims |
| Telling the agent the training procedure | Intended: it's information about the environment, and random gets the same procedure. Disclosed in the writeup. |
| The 256-example validation set is extra labeled data (same as Phase 1) | Identical for every arm. State it. |
| gridnav_hidden's pool caps the top budget at about 3,000-3,600 | Pool rule; report the actual budget |
| Multiple comparisons | Primary = 3 families × budgets 16 and 64. Everything else is secondary or exploratory. |
| One model and one harness (Claude Code, `noexec`) | Stated; Codex is a candidate follow-up (Part C) |
| Instances as fixed effects; pooling across them | Claims rest on per-instance consistency; pooled numbers are descriptive |

### B.12 Implementation checklist (for Claude Code)
Implement exactly as written. Where this plan is ambiguous or conflicts with current code, stop and ask; don't choose.

**Part A**
1. `docs/DECISIONS.md`: the A.2 exclusion rule, with the disclosure that it was written after sample_00 was observed, and the A.5 supersession of `main_v1` digits rows.
2. `experiment.py`: the A.4 pool rule, with tests. Budget above the pool becomes the pool size; duplicates are dropped; keys use the actual budget. Confirm it changes no existing `main_v1` job key for gridnav, ring2d or sparse_parity.
3. `configs/digits_v1b.yaml` as in A.5.

**Part B**

4. **Tasks.** `parity_hidden`, `ring_hidden` and `gridnav_hidden` families with instances 0-2, drawn as in B.5. Registry names `<family>_i<k>`, a `family` attribute, and init lookup by family.
5. **Specs.** Spec text verbatim from B.4.
6. **Objective.** `prompts/objectives/finetune_family.md` as in B.6, with placeholders filled from a config file passed to `generate_init.py` (`--config configs/phase2.yaml`). Test that the rendered values equal the config.
7. **Generation for a family.** `generate_init.py --task <family>` generates a family-level sample. The prompt is the family spec, identical for every instance.
8. **Tests.**
   - B.10 blinding tests and instance constraints.
   - parity_hidden: an init that computes parity of the Phase 1 subset scores 0.5 ± 0.04 on each instance.
   - gridnav_hidden:
     - BFS correctness on hand-built cases.
     - The tie-break rule.
     - The label equals the wall-free rule whenever that move begins a shortest path.
     - Free-cell connectivity.
     - Disjoint splits.
   - ring_hidden: the inside fraction of each instance falls in [0.20, 0.50] on a large sample.
9. **Reference inits.** Pipeline-test references per family, never reported:
   - parity: equal weights on all 16 bits feeding the Phase 1 ladder, extended to 17 rungs (relu(s − k), k = 0..16) so it computes the parity of all 16 bits;
   - ring: r² with thresholds at the midpoint of each radius's feasible range under all the spec constraints together: r_in in [0.10, 0.80] gives 0.45, and r_out in [sqrt(0.01 + 0.8/π) ≈ 0.514, 0.95] gives ≈ 0.732;
   - gridnav: the wall-free rule.
   Plus `configs/phase2_smoke.yaml`.
10. **Configs.** `configs/phase2.yaml`: families × instances as tasks, the six arms with source `claude-opus-5-5__claudecode-noexec__finetune_family`, seeds 0-5, and the B.7 budgets.
11. **Analysis.** `analyze.py`:
    - a family summary section with the B.8 primary table (per instance: written − random at 16 and 64, with CI, and the count of instances with CI > 0);
    - the samples-to-target table;
    - zero-shot per sample per instance;
    - the pooled-controls table per family (B.8 secondary 4) at every budget measured in all instances, with the instance-stratified bootstrap CI and the H10 check (CI lower bound > 0 at 16, 64 and 256);
    - an H9 canary line printed at the top of each parity_hidden section.
12. **DECISIONS entry.** A v1.0 entry: "Phase 2 pre-registered in docs/PHASE2_PLAN.md at commit <hash>", added after the commit.

Then run pytest, run `configs/phase2_smoke.yaml` and analyze it, and show Garrett the dry-run prompt for each family. Don't generate anything and don't start real sweeps.

### B.13 Run order and stopping rules
1. Implement (B.12), review the diff, pytest, smoke.
2. **Pre-registration lock:** commit everything, then add the commit hash to DECISIONS.
3. Check `claude --version`; rerun the isolation check if it changed.
4. Dry-run each family's prompt and read it for any instance information.
5. Generate the digits replacement(s) (A.3) and 3 samples per family. Audit all of them.
6. Run `configs/digits_v1b.yaml` → `main_v1_digits`, then `configs/phase2.yaml` → `phase2_v1`, and analyze both.
7. Read results in this order: H9 canary, then the primary table, then secondary.

**Stopping rules:**
- An H9 parity value outside the band halts reading until it's explained.
- An instance violating its constraints is a bug. Fix it, rerun that instance under a new run name, and log it.
- Nothing in this document changes after step 2 except through dated amendments.

### B.14 Cost
- **Generation:** about 10 agent sessions (1 or more for digits, plus 9 for the families).
- **Phase 2 sweep:** 3 families × 3 instances × 6 arms × 6 budgets × 6 seeds = 1,944 jobs, each with the 10-config grid, about 3x the 660 jobs in `main_v1`.
- **Digits rerun:** about 180 jobs.

---

## Part C: After Phase 2 (candidates, not pre-registered)
1. **Objective ablation on Phase 1 tasks** (`zero_shot` vs `finetune_friendly`), motivated by the margin observation: does "keep logits moderate" produce worse starting points?
2. **Codex as a second model family.** Needs its own study profile and isolation check.
3. **The `tools` condition (H6).**
4. **Muon vs AdamW** (`configs/muon_extension.yaml`; verify the numpy Muon first).
5. **More samples per family** (6 or more), for a real per-sample analysis.

---

## Amendments
(Dated entries only. Nothing here before the pre-registration commit.)

- 2026-11-04, written before any Phase 2 sweep of written samples (only phase2_smoke_20261104_101051, reference inits only, has run). Per their audits, the exact zero-shot accuracy over all 2^16 inputs of each parity_hidden sample lies inside H9's band for every one of the 1,820 possible subsets: sample_00 0.502-0.515, sample_01 0.5074, sample_02 0.4935-0.5145. No sample's zero-shot predictions can therefore track any instance's subset, and no construction-based explanation for an H9 OUTSIDE exists. An OUTSIDE for any of these samples is investigated in this order: (1) confirm the swept weights are byte-identical to the audited weights.npz; (2) confirm the instance's labels are wired correctly; (3) compute the sample's exact accuracy over all 2^16 inputs for that instance; if it is inside the band, the OUTSIDE is test-set noise (2,000 of 65,536 inputs) and is reported as such. Separately, 52 subsets have at most 2 relevant bits in any of sample_02's blocks; that bears on how fast it fine-tunes, not on H9. The registered H9 verdict is unchanged.

- 2026-11-04. Follow-up F1, written after phase2_v1 results. Hypotheses below come from phase2_v1 and are confirmatory only because the instances are new.
  - Instances: three new parity_hidden instances i3, i4, i5, drawn by the B.5 method with seeds [2026, 11, 4, 1, i] for i = 3, 4, 5, distinct from i0-i2 and the Phase 1 subset.
  - Inits: the same three audited parity_hidden samples (no regeneration). Same six arms.
  - Budgets: 0, 16, 64, 96, 128, 192, 256, 384, 512, 1024. Seeds 0-11 (4 per sample per instance). Everything else as phase2.yaml.
  - Primary (F1a): written - random at budget 256, paired by seed; supported if the 95% CI lower bound > 0 in at least 2 of 3 new instances.
  - Secondary (F1b): samples-to-target at 0.95 and 0.99 on the finer grid, random/written ratio per instance.
  - Exploratory (F1c): per sample, the share of (instance, seed) cells that reach test accuracy >= 0.95 at budget 128 (that one training run per cell, not the best of budgets <= 128). And an analytic probe with no training: for each sample and instance (i0-i5) with relevant subset S, the label-dependent first-layer gradient D(S) = the W0 loss gradient with the true labels minus the W0 loss gradient with soft labels (0.5, 0.5), computed exactly over all 2^16 inputs at initialization. The cross-entropy gradient is linear in the targets, so D(S) is exactly its label-dependent part. Reported per sample and instance: (a) the share of ||D(S)||^2 on S's 4 rows of W0 (squared Frobenius norm over W0 rows, b0 excluded; even spread 0.25); (b) ||D(S)|| / ||full W0 gradient||, so "no label signal" is distinguishable from "signal spread out"; (c) the rank of S among all 1,820 four-bit subsets by the energy of D(S) on their rows (1 = most; ties count against S). If ||D(S)|| is numerically zero (at most 1e-9 of the full W0 gradient's norm), the result is "no label signal", not a share. Output: results/parity_probe_f1/. This tests directly whether written inits point gradient descent at the hidden subset (the claim in s01's audit). The probe's definition and the cell-share rule were settled on 2026-11-04, before any probe result existed.

- 2026-11-04. F1c probe extension (exploratory), added after seeing the F1c probe output (results/parity_probe_f1/), before any F1 sweep result was read. (1) Baselines on i0-i5 with the same (a), (b), (c): random He init (20 seeds, seeds 0-19 of the sweep's init stream), plus norm_matched and shuffled_noise of each written sample (seeds 0-5, built with the sweep's streams and the phase2_parity_f1.yaml arm names). (2) A fourth quantity (d), the absolute ||D(S)||, for every row, written and baseline, since signal strength, not just direction, should matter with finite data. (3) For each written sample, (c) with each of all 1,820 four-bit subsets as the hidden subset (the inits are instance-agnostic), reported as the distribution of ranks. Output: results/parity_probe_f1_baselines/. results/parity_probe_f1/ is unchanged.
