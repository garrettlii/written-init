"""Have a headless coding agent write initial weights for a task. No API keys:
uses your Claude Code / Codex CLI login.

Always start with --dry-run: it prints the prompt and the exact command.

  uv run python scripts/generate_init.py --task gridnav --agent claude --model claude-opus-5-5 --condition noexec --dry-run
  uv run python scripts/generate_init.py --task gridnav --agent claude --model claude-opus-5-5 --condition noexec --n-samples 3
  uv run python scripts/generate_init.py --task gridnav --agent codex  --model gpt-6.1-sol    --condition ro --n-samples 3
  uv run python scripts/generate_init.py --task ring_hidden --agent claude --model claude-opus-5-5 --condition noexec \
      --objective finetune_family --config configs/phase2.yaml --dry-run   # Phase 2: --task is a family

Conditions:  claude: noexec | tools     codex: ro | tools
Run scripts/check_isolation.py for each (agent, condition) before the first real run.
"""

import argparse
import json
from pathlib import Path

from written_init.agents import CONDITIONS, WRITABLE
from written_init.agents.generate import DEFAULT_MAX_TURNS, generate_one, source_name
from written_init.agents.prompts import objectives, task_prompt
from written_init.agents.runners import claude_cmd, claude_settings, cli_version, codex_cmd
from written_init.paths import ROOT
from written_init.experiment import SweepConfig
from written_init.tasks import FAMILIES, generation_targets, spec_task


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--task", required=True, choices=generation_targets(),
                   help="a Phase 1 task or a Phase 2 family (one sample serves all of its instances)")
    p.add_argument("--agent", required=True, choices=sorted(CONDITIONS))
    p.add_argument("--model", required=True, help="model id passed to the CLI, recorded in the source name")
    p.add_argument("--condition", required=True)
    p.add_argument("--objective", default="zero_shot", choices=objectives())
    p.add_argument("--config", type=Path, default=None,
                   help="sweep config that fills the objective's placeholders (finetune_family: configs/phase2.yaml)")
    p.add_argument("--n-samples", type=int, default=1)
    p.add_argument("--max-retries", type=int, default=1, help="format/rule retries only")
    p.add_argument("--max-turns", type=int, default=None, help="Claude Code only")
    p.add_argument("--timeout-min", type=float, default=30)
    p.add_argument("--keep-workspace", action="store_true", help="leave the temp workspace for inspection")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()

    if a.condition not in CONDITIONS[a.agent]:
        p.error(f"--agent {a.agent} supports --condition {' | '.join(CONDITIONS[a.agent])}")
    task = spec_task(a.task)
    cfg = SweepConfig.load(a.config) if a.config else None

    if a.dry_run:
        prompt = task_prompt(task, a.agent, a.condition, a.objective, cfg)
        print("=== PROMPT ===\n" + prompt + "\n")
        ws = Path("<temp workspace>")
        if a.agent == "claude":
            cmd = claude_cmd("<prompt>", a.model, a.condition, Path("<sample>/claude_settings.json"),
                             a.max_turns or DEFAULT_MAX_TURNS[a.condition])
            print("=== COMMAND (cwd = temp workspace) ===\n" + " ".join(repr(c) if " " in c else c for c in cmd))
            print("\n=== claude_settings.json ===\n" + json.dumps(claude_settings(ROOT), indent=2))
        else:
            cmd = codex_cmd(a.model, a.condition, ws, Path("<sample>/attempt0.final.md"))
            print("=== COMMAND (prompt on stdin) ===\n" + " ".join(repr(c) if " " in c else c for c in cmd))
        print(f"\n{a.agent} CLI: {cli_version(a.agent)}")
        if a.task in FAMILIES:
            print(f"family: one sample per session, used for every instance of {a.task}")
        print(f"output: inits/{a.task}/{source_name(a.agent, a.model, a.condition, a.objective)}/sample_XX/")
        print(f"agent writes build.py: {(a.agent, a.condition) in WRITABLE}; numpy venv: {a.condition == 'tools'}")
        print(f"[dry run] would start {a.n_samples} agent session(s) (+ up to {a.max_retries} retries each)")
        return

    for _ in range(a.n_samples):
        d = generate_one(a.task, a.agent, a.model, a.condition, a.objective, a.max_retries,
                         a.max_turns, int(a.timeout_min * 60), a.keep_workspace, a.config)
        meta = json.loads((d / "meta.json").read_text())
        reds = [f["message"] for f in meta["transcript_flags"] if f["severity"] == "red"]
        print(f"[{meta['status']}] {d.relative_to(ROOT)}  attempts={len(meta['attempts'])}  "
              f"red_flags={len(reds)}")
        for r in reds:
            print(f"   ! {r}")
        if meta["status"] != "ok":
            print("   reason:", meta["final_message"][:300])
        if meta["status"] == "fence_violation":
            print("\nStopping: the agent's tool set did not match the fence, so every further session would "
                  "too. Rerun scripts/check_isolation.py and fix src/written_init/agents/runners.py first.")
            raise SystemExit(2)


if __name__ == "__main__":
    main()
