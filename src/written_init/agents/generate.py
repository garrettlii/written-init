"""Generate one written init with a headless agent.

Output layout (same sample_XX convention the sweep already reads):
    inits/<task>/<source>/sample_XX/
        prompt.md                  exact task prompt
        attemptN.transcript.jsonl  full agent event stream (audit this)
        attemptN.stderr.log
        attemptN.session.jsonl     Claude Code's own session log, redacted (Claude only, v0.8)
        attemptN.final.md          Codex final message (Codex only)
        claude_settings.json       sandbox/permission settings passed to Claude Code
        workspace/                 snapshot of the agent's folder (build.py, NOTES.md, ...)
        response.md                NOTES.md or the final message: the model's explanation
        build.py                   the code that was executed
        weights.npz                output of build_weights()
        meta.json                  agent, CLI version, condition, attempts, flags, audit status

Retries (format/rule failures only) are fresh agent runs in the same workspace
with the error appended to the prompt. The agent never sees accuracy or data.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from ..init_arms import validate
from ..paths import INITS, RESULTS, ROOT
from ..sandbox import check_source, extract_code, run_build
from ..experiment import SweepConfig
from ..tasks import spec_task
from . import CONDITIONS, WRITABLE
from .prompts import prompt_hash, retry_section, task_prompt
from .runners import check_profile, cli_version, fence_violation, redact_cmd, run_agent
from .transcript import flags, latest_isolation_roster, parse, roster_flag
from .workspace import STUB, cleanup, make_workspace, snapshot

DEFAULT_MAX_TURNS = {"noexec": 15, "ro": 15, "tools": 60}
ISOLATION = RESULTS / "isolation"


def source_name(agent: str, model: str, condition: str, objective: str = "zero_shot") -> str:
    harness = {"claude": "claudecode", "codex": "codex"}[agent]
    s = f"{model}__{harness}-{condition}"
    return s if objective == "zero_shot" else f"{s}__{objective}"


def next_sample_dir(task_name: str, source: str) -> Path:
    root = INITS / task_name / source
    root.mkdir(parents=True, exist_ok=True)
    ids = [int(p.name.split("_")[1]) for p in root.iterdir() if p.is_dir() and "_" in p.name
           and p.name.split("_")[1].isdigit()]
    d = root / f"sample_{(max(ids) + 1 if ids else 0):02d}"
    d.mkdir()
    return d


def _collect_code(ws: Path, final_text: str, writable: bool) -> str | None:
    if writable and (ws / "build.py").exists():
        code = (ws / "build.py").read_text()
        if code.strip() != STUB.strip():
            return code
    return extract_code(final_text or "")


def _validate(task, code: str | None, out_dir: Path) -> tuple[bool, str]:
    if code is None:
        return False, "No build.py with a build_weights() function was produced."
    (out_dir / "build.py").write_text(code)
    problems = check_source(code)
    if problems:
        return False, "The code breaks these rules:\n" + "\n".join(f"- {p}" for p in problems)
    ok, msg = run_build(out_dir / "build.py", out_dir / "weights.npz")
    if not ok:
        return False, msg
    with np.load(out_dir / "weights.npz") as f:
        params = {k: f[k] for k in f.files}
    try:
        validate(task, params)
    except ValueError as e:
        (out_dir / "weights.npz").unlink(missing_ok=True)
        return False, f"build_weights() returned invalid parameters: {e}"
    return True, "ok"


def generate_one(task_name: str, agent: str, model: str, condition: str, objective: str = "zero_shot",
                 max_retries: int = 1, max_turns: int | None = None, timeout_s: int = 1800,
                 keep_workspace: bool = False, cfg_path: Path | None = None) -> Path:
    """task_name is a Phase 1 task or a Phase 2 family. cfg_path fills objective placeholders."""
    if condition not in CONDITIONS.get(agent, ()):
        raise ValueError(f"{agent} supports conditions {CONDITIONS.get(agent)}, not {condition!r}")
    check_profile(agent)  # fail before creating any sample folder
    task = spec_task(task_name)
    cfg = SweepConfig.load(cfg_path) if cfg_path else None
    writable = (agent, condition) in WRITABLE
    max_turns = max_turns or DEFAULT_MAX_TURNS[condition]
    base_prompt = task_prompt(task, agent, condition, objective, cfg)
    out_dir = next_sample_dir(task_name, source_name(agent, model, condition, objective))
    (out_dir / "prompt.md").write_text(base_prompt)

    roster_ref = latest_isolation_roster(agent, condition, ISOLATION) if agent == "claude" else None
    ws = make_workspace(writable=writable, with_python=(condition == "tools"))
    attempts, all_flags, last_run = [], [], None
    ok, msg, prompt, violation = False, "", base_prompt, None
    try:
        for attempt in range(max_retries + 1):
            tag = f"attempt{attempt}"
            run = run_agent(agent, condition, model, prompt, ws, out_dir, ROOT, tag,
                            max_turns=max_turns, timeout_s=timeout_s)
            last_run = run
            parsed = parse(agent, run.transcript, ws, run.session_log)
            fl = flags(parsed, agent, condition, ws, ROOT)
            if agent == "claude" and (rf := roster_flag(parsed["agents"], roster_ref)):
                fl.append(rf)
            all_flags += [{**x, "attempt": attempt} for x in fl]
            violation = fence_violation(agent, condition, parsed["available_tools"],
                                        parsed["hook_events"], parsed["plugins"], parsed["skills"],
                                        parsed["request_tools"], parsed["server_blocks"])
            if violation:
                # Fail closed: never keep output from a session whose tool set wasn't the designed one.
                ok, msg = False, f"fence violation: {violation}"
            elif run.timed_out:
                ok, msg = False, f"agent run exceeded {timeout_s}s"
            else:
                ok, msg = _validate(task, _collect_code(ws, run.final_text, writable), out_dir)
            attempts.append({
                "attempt": attempt, "ok": ok, "message": msg, "returncode": run.returncode,
                "timed_out": run.timed_out, "seconds": run.seconds, "num_turns": parsed["num_turns"],
                "cost_usd_estimate": parsed["cost_usd"], "usage": parsed["usage"],
                "available_tools": parsed["available_tools"], "reported_model": parsed["model"],
                "plugins": parsed["plugins"], "n_hook_events": len(parsed["hook_events"]),
                "skills": parsed["skills"], "agents": parsed["agents"],
                "session_log": run.session_log.name if run.session_log else None,
                "request_tools": parsed["request_tools"], "n_server_blocks": len(parsed["server_blocks"]),
                "session_error": parsed["session_error"],
                "n_commands": len(parsed["commands"]), "n_tool_calls": len(parsed["tool_calls"]),
            })
            if ok or run.timed_out or violation:
                break
            prompt = base_prompt + "\n\n" + retry_section(msg, writable)
        snapshot(ws, out_dir / "workspace")
        notes = ws / "NOTES.md"
        (out_dir / "response.md").write_text(notes.read_text() if notes.exists()
                                             else (last_run.final_text if last_run else ""))
    finally:
        if not keep_workspace:
            cleanup(ws)

    weight_stats = None
    if ok:
        with np.load(out_dir / "weights.npz") as f:
            allw = np.concatenate([f[k].ravel() for k in f.files])
        weight_stats = {"n": int(allw.size), "frac_zero": float((allw == 0).mean()),
                        "max_abs": float(np.abs(allw).max())}
    else:
        (out_dir / "weights.npz").unlink(missing_ok=True)  # the sweep must never pick it up

    meta = {
        "task": task_name, "agent": agent, "cli_version": cli_version(agent), "model": model,
        "condition": condition, "objective": objective,
        "objective_config": str(cfg_path) if cfg_path else None,
        "status": "ok" if ok else ("fence_violation" if violation else "failed"),
        "final_message": msg, "attempts": attempts, "command": redact_cmd(last_run.cmd) if last_run else None,
        "transcript_flags": all_flags, "n_red_flags": sum(x["severity"] == "red" for x in all_flags),
        "weight_stats": weight_stats, "prompt_hash": prompt_hash(base_prompt),
        "profile": last_run.profile if last_run else None,
        "stripped_env": last_run.stripped_env if last_run else None,
        "workspace_kept": str(ws) if keep_workspace else None,
        "created": datetime.now(timezone.utc).isoformat(), "audited": False,
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2))
    return out_dir
