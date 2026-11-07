# Research plan: is an LLM-written initialization worth training data?

## Question

Recent work (Takehi, Teoh, Zhang & Khattab, "Sparks of Weight-Space Programming", MIT CSAIL, Nov 2026) shows frontier LLMs can write small networks' weights directly from a task description. That work evaluates the written networks as finished products. This project asks a different question: **used as an initialization for gradient training on small datasets, how many training examples is a written init worth?**

The answer is expressed as a **data multiplier**: if the written-init arm reaches accuracy *a* with *n* examples and random init needs *m* examples to reach *a*, the multiplier is *m / n*.

Weights are written by headless coding agents (Claude Code, Codex CLI) in isolated workspaces with controlled tools, which also makes **tool access** an experimental variable: does an agent that can run its own checks write better initializations than one that must reason it out?

This connects weight-space programming to data efficiency: the written init carries knowledge from the LLM's pretraining and from the task spec into the network without any examples. Related baseline for data-limited training: Kim et al., "Pre-training under infinite compute" (ICLR 2026).

## Hypotheses (pre-registered; record any change in docs/DECISIONS.md)

- **H1.** Written inits give multipliers well above 1 at small budgets (16-64) on tasks whose spec determines a simple algorithm (sparse_parity, gridnav).
- **H2.** The multiplier shrinks as the budget grows, approaching 1 once random init has enough data.
- **H3.** The gain comes from structure, not scale: written_noise beats shuffled_noise (same values, same noise, arrangement destroyed), and written beats norm_matched (same per-tensor norms, random directions). (Revised in v0.3; see docs/DECISIONS.md.)
- **H4.** The advantage tracks task writability: largest on sparse_parity and gridnav, smaller on ring2d, near 1 on digits8x8.
- **H5 (exploratory).** Plain written inits fine-tune worse than they could because of unused or dead units; written_noise recovers some of this.
- **H6 (exploratory).** Agents allowed to execute code (`tools`) produce higher zero-shot accuracy than the same model without execution (`noexec`), with a smaller difference after fine-tuning.

A result against any of these is still a result. Write it up either way.

## Design

### Tasks

| task | input | classes | net | writability | why it's here |
|---|---|---|---|---|---|
| sparse_parity | 16 bits | 2 | 16-64-64-2 | high | known to be slow for SGD from random init; trivial once you know the bits |
| gridnav | 2 one-hots on 9x9 grid | 5 | 162-64-64-5 | high | small policy, like the MIT game networks, but supervised |
| ring2d | point in [-1,1]^2 | 2 | 2-32-32-2 | medium | curved boundary from ReLUs takes craft |
| digits8x8 | 8x8 image | 10 | 64-64-32-10 | low | visual knowledge only; the low-writability control |

### Arms

| arm | what it tests |
|---|---|
| random | He-initialized baseline |
| written | agent weights as written |
| written_noise | written + 0.1 x He-scale noise: do revived units help fine-tuning? |
| shuffled_noise | written values permuted within each tensor, plus the same noise. **Primary structure control** (vs written_noise): both start equally trainable |
| norm_matched | random directions with written per-tensor norms. **Scale control** (vs written) |
| shuffled | permuted, no noise. **Secondary only**: mostly-zero written weights leave a shuffled net with most ReLU units dead (measured: 0-6% of layer-2 units alive on the sparse_parity reference), so it can lose to random for reasons unrelated to structure |

Later arms (extensions): a second agent/model, the `tools` condition, the finetune_friendly prompt objective, Muon.

### Generation conditions

| source suffix | agent | can execute code? | primary use |
|---|---|---|---|
| `__claudecode-noexec` | Claude Code | no (enforced) | main arm: closest to "pure reasoning" |
| `__claudecode-tools` | Claude Code | numpy-only Python, OS-sandboxed | H6 |
| `__codex-ro` | Codex | read-only commands possible (cannot be disabled), flagged | second model family |
| `__codex-tools` | Codex | Python in workspace, no network | H6 for the second family |

Each source is analyzed separately. The fence for each lives in `src/written_init/agents/runners.py` and is verified with `scripts/check_isolation.py` per CLI version.

### Protocol

- Budgets: 0, 16, 64, 256, 1024, 4096 (digits capped at its 1,000-example pool). Budget 0 means no training.
- Seeds: 5. Each seed fixes the training subset (same for all arms), minibatch order, random init, and which LLM sample is used (`seed mod n_samples`). Generate at least 3 samples per (task, source) so agent variability is part of the error bars.
- Training: AdamW, batch 64, up to 3,000 steps, early stopping on validation (patience 10 evals of 50 steps). Step 0 is an eligible checkpoint.
- Tuning: identical grid for every arm and budget (lr {1e-4, 3e-4, 1e-3, 3e-3, 1e-2} x weight decay {0, 0.1}), selected on validation accuracy, reported on test.
- Every LLM sample is audited before the main sweep (`require_audited: true`).

## Metrics

- **Zero-shot accuracy** of each written init, and its **zero-shot worth**: the number of examples random init needs to match it.
- **Fine-tuned test accuracy vs budget** per arm, with 95% bootstrap CIs over seeds.
- **Data multiplier** per (arm, budget), log-linear interpolation on random's curve, with bootstrap CIs. Values outside random's measured range are censored and reported as bounds (`>=` / `<=`), never as point estimates.
- **Step-0 selection rate**: how often validation preferred the untrained init, a direct sign that fine-tuning hurt.
- **Control comparisons**: test-accuracy differences written_noise - shuffled_noise and written - norm_matched per budget, paired by seed (same training data), with bootstrap CIs (`comparisons.csv`).
- **When the multiplier is withheld** (v0.3): no multiplier when the arm is within the margin (default 0.02, or its CI half-width if larger) of a majority-class predictor; only an interval when random's curve doesn't clearly rise between the bracketing budgets; every point estimate reported with its bracket, since interpolating inside a sudden jump (sparse_parity) is an assumption.

## Threats to validity, and what we do about each

| threat | mitigation |
|---|---|
| The agent fits weights instead of writing them (enumerates inputs, hand-rolls gradient descent, tunes numbers by trial and error in `tools`) | static checks on build.py, automatic transcript flags, mandatory audit of build.py and the full transcript; report rejection counts per source |
| The agent sees things it shouldn't (repo, data, web) | temp workspace outside the repo; per-condition tool fence; `check_isolation.py` per CLI version; transcript flags for any outside path, web call or denial |
| User configuration reaches the agent (plugins, hooks, global instructions, skills); this contaminated the first real sample via a plugin SessionStart hook | v0.5: dedicated empty study profiles per agent; disableAllHooks; any hook event or loaded plugin is a fence violation; isolation check probes hooks, plugins and a self-report of extra instructions |
| Known fence gap: Codex can read files outside its workspace | audit Codex transcripts for outside paths; state it in the writeup |
| CLI or model versions change mid-study | CLI version and reported model saved per sample; rerun the isolation check after upgrades; don't pool samples across a major CLI change without checking |
| Hyperparameter grid favors one arm (written inits may need tiny lr) | same grid for all arms; grid includes small lrs; report selected hp per arm |
| Validation set is extra labeled data | identical across arms; state it in the writeup; optional follow-up with budget-proportional validation |
| Censored multipliers look like point estimates | report as bounds; extend budgets downward or upward if many are censored |
| Prompt sensitivity | fixed templates in prompts/; any change logged; objective variant tested as an extension |
| Contamination (sparse parity and gridnav-style constructions are well known) | that's part of the claim: the LLM brings prior knowledge; digits8x8 is the control where knowledge alone is harder to use |
| Single model family | add a second agent (Codex) before making general claims |
| Small sample of agent outputs | at least 3 samples per (task, source); report per-sample variance |
| Shuffled control is confounded by dead units (written weights are mostly zeros) | v0.3: primary structure control is shuffled_noise vs written_noise; norm_matched added for scale; plain shuffled reported as secondary; each sample's zero fraction in meta.json |
| Multipliers computed against a flat or at-chance random curve look precise but are noise | v0.3: chance and flat-segment rules withhold or widen the estimate; brackets always reported |
| numpy Muon could be buggy | Muon is an extension only; verify against a reference implementation first |

## Milestones

- [ ] **Week 1: pipeline.** `uv sync`, tests pass, `/smoke` runs end to end. Read every file in `src/` and make sure you agree with it. Change anything you disagree with now, before any data exists, and log it.
- [ ] **Week 2: generation.** Run `check_isolation.py` for the conditions you'll use. Dry-run every task's prompt and read it critically. Generate 3 samples per task with `claude ... noexec`. Audit all of them, transcripts included. Note zero-shot accuracies.
- [ ] **Week 3: main sweep.** Run `configs/default.yaml`, analyze, sanity-check (does random init on sparse_parity behave as expected? do curves rise with data?). Look at failures before successes.
- [ ] **Week 4: robustness.** Codex as a second model family, the `tools` condition (H6), or the finetune_friendly objective, whichever the week 3 results make more interesting. Rerun analysis.
- [ ] **Week 5: writeup.** Short post with plots and a multiplier table, the full code and agent transcripts on GitHub. Cite the MIT post.
  - [ ] Before publishing, run a scrub script over `inits/` and `results/` that removes emails, account/org UUIDs and home paths (`claude_settings.json` and the v0.8 backfill `report.json` both contain them; `redact_log` in `agents/runners.py` already does this for session logs). It writes to a separate `publish/` folder and never edits in place. Verify with a grep over `publish/` that finds 0 matches.

## Extensions (pick after the main result)

1. **Muon vs AdamW under written init** (`configs/muon_extension.yaml`): does Muon's orthogonalized update preserve or erase written structure faster?
2. **Lottery tickets in written nets**: prune the fine-tuned written network and rewind to the written init vs to random. Is the written init a better ticket?
3. **Objective ablation**: zero_shot vs finetune_friendly prompts. Does telling the LLM about fine-tuning change the multiplier?
4. **Partial writing**: let the LLM write only the first layer (features), with the rest random.
5. **Bigger nets with tools**: give the LLM a Python inspector for networks that don't fit in context.

## Writeup outline

1. One-paragraph question and headline number (with CI and task).
2. Setup in a figure: spec -> LLM -> weights -> fine-tune on n examples.
3. Accuracy vs budget per task, all arms.
4. Multiplier table, censoring marked.
5. Shuffled control and what it rules out.
6. Where it fails (digits, any rejected samples, any step-0 selections).
7. Limitations, then extensions.
