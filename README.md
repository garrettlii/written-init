# written-init

**Is an LLM-written initialization worth training data?** A headless coding agent (Claude Code or Codex CLI) writes a small network's weights from a task description alone. We then fine-tune on 16 to 4,096 examples and measure how much more data random init needs to match it. See `PLAN.md` for the research design.

## Environment

Requirements: Python 3.11+, [uv](https://docs.astral.sh/uv/), and at least one of the [Claude Code](https://code.claude.com/docs) or [Codex](https://developers.openai.com/codex) CLIs. No API keys: agents run on your subscription login, inside a dedicated study profile (`scripts/setup_profiles.py`, one-time). Training runs on a laptop CPU.

```bash
uv sync                                       # creates .venv
uv run pytest                                 # 58 tests, no agents or network needed
uv run python scripts/build_reference.py      # builds the hand-made reference inits
uv run python scripts/run_sweep.py --config configs/smoke.yaml
uv run python scripts/analyze.py results/smoke
```

In `results/smoke/report.md`, the `reference` arm should hit ~100% at budget 0 while `random` needs ~1,000 examples. That pattern is the pipeline working, not a finding: reference inits are hand-built test fixtures.

## Agents and conditions

Each (agent, condition) is its own experimental source with its own tool fence. The fence is defined in one place, `src/written_init/agents/runners.py`, and tested in `tests/test_agents.py`.

| agent | condition | what the agent can do | how it's enforced |
|---|---|---|---|
| Claude Code | `noexec` | exactly Read, Write, Edit, in its workspace | `--tools Read,Write,Edit` fixes the tool set; startup tool list verified every run (fail-closed); home dir and repo denied to file tools; `--strict-mcp-config` |
| Claude Code | `tools` | the above + Bash, pre-approved only for `.venv/bin/python` (numpy only) | `--tools Read,Write,Edit,Bash`; OS sandbox with no network, home dir and repo unreadable except the Python install, unsandboxed retries off |
| Codex | `ro` | think and reply with code; can't write files | `codex exec -s read-only`, web search disabled, user config ignored. Codex can't disable its shell, so read-only commands can still run; they're flagged |
| Codex | `tools` | write build.py and run Python in its workspace | `-s workspace-write` (writes limited to workspace + temp, no network) |

Every session runs in a fresh temp folder **outside** the repo (so no project `CLAUDE.md` or code is visible), with the CLI pointed at a **dedicated, empty study profile** (`CLAUDE_CONFIG_DIR=~/.claude-written-init`, `CODEX_HOME=~/.codex-written-init`), so your plugins, hooks, global instructions and skills never load. The profile also turns off claude.ai account sync (`syncClaudeAiSkills`, `syncClaudeAiPlugins`), which otherwise downloads your account's skills and plugins into every profile you log into. API keys are stripped from the agent's environment so billing stays on the subscription login. The full event stream is saved as `attemptN.transcript.jsonl` and scanned; any extra tool, hook or plugin stops the sample.

**Known gap, stated plainly.** Codex sandboxes restrict writes and network, not reads, so a Codex agent that went looking could read files elsewhere on disk; the transcript audit is the control there.

**Verify before trusting.** `scripts/check_isolation.py` runs a real session with the same fence and asks the agent to try forbidden things (read canary files in the repo and your home directory, use the network, write outside its folder, import sklearn, ...), then checks what actually happened. It also FAILS if Claude Code reports any tool beyond the designed set, and for `tools` it checks that Python still works under the sandbox. Run it once per (agent, condition) and again after every CLI upgrade, because flags drift between versions.

## Workflow

```
check_isolation.py ──► results/isolation/<agent>_<condition>_<time>/report.json   (once per agent/condition/CLI version)

task spec ──► generate_init.py ──► temp workspace ──► claude -p / codex exec
                                                          │
                     inits/<task>/<model>__<harness>-<condition>/sample_XX/
                     (prompt, transcripts, workspace snapshot, build.py, weights, meta + red flags)
                                                          │
                                  /audit-init ──► mark_audited.py
                                                          │
configs/*.yaml ──► run_sweep.py ──► results/<run>/ ──► analyze.py ──► report.md, multipliers.csv, figures/
```

0. **Once:** `uv run python scripts/setup_profiles.py --agent claude` (creates the study profile and logs it in)
1. **Check the fence:** `uv run python scripts/check_isolation.py --agent claude --model claude-opus-5-5 --condition noexec`
2. **Read the prompt and command:** `uv run python scripts/generate_init.py --task gridnav --agent claude --model claude-opus-5-5 --condition noexec --dry-run`
3. **Generate** (replace `--dry-run` with `--n-samples 3`). Run it in a normal terminal; each session can take several minutes.
4. **Audit** every sample, then `uv run python scripts/mark_audited.py <sample_dir> --notes "..."` (or `--reject`).
5. **Sweep:** `uv run python scripts/run_sweep.py --config configs/default.yaml --name main_v1` (resumable).
6. **Analyze:** `uv run python scripts/analyze.py results/main_v1`

## Layout

```
written-init/
├── PLAN.md, docs/            DECISIONS.md, PHASE2_PLAN.md, writeup.md
├── configs/                smoke.yaml, default.yaml, muon_extension.yaml
├── prompts/                system.md, agent_task.md, conditions/, objectives/, retry.md
├── src/written_init/
│   ├── tasks/              sparse_parity, ring2d, gridnav, digits8x8
│   ├── agents/             runners (the fence), workspace, transcript (+ flags), prompts, generate
│   ├── models.py, optim.py, train.py, init_arms.py, experiment.py, metrics.py, sandbox.py, seeding.py
├── scripts/                setup_profiles, generate_init, check_isolation, run_sweep, analyze, build_reference, mark_audited
├── inits/                  written weights (reference/ = test fixtures only)
├── results/                sweeps, isolation reports
└── tests/                  includes fake claude/codex CLIs for offline testing
```

## Notes

- Model ids go straight to the CLI (`--model` for Claude Code, `-m` for Codex) and into the source folder name, so always pass one explicitly.
- The Muon optimizer is implemented for the extension but only lightly tested. Verify it against a reference implementation before reporting Muon results.
