"""Build and run headless agent commands.

The fence for each (agent, condition) is defined HERE and nowhere else, so it is
easy to review and test. Run scripts/check_isolation.py after editing this file
or upgrading either CLI: flags drift, and the check is how you find out.

Claude Code (`claude -p`)
  The tool SET is fixed with --tools (v0.4). --allowedTools only pre-approves
  calls; it never removed anything, and unlisted tools that need no approval
  still ran (the v0.3 isolation check showed 20 tools in noexec, including
  PublishPlugin, SendMessage, CronCreate and Skill). Every run also verifies
  the tool list Claude Code reports at startup against EXPECTED_TOOLS and
  stops if anything extra appears (fail-closed).
  noexec  tools: exactly Read, Write, Edit.
  tools   exactly Read, Write, Edit, Bash. Bash is pre-approved only for
          `.venv/bin/python ...`, and runs inside Claude Code's OS sandbox
          (Seatbelt on macOS, bubblewrap on Linux) with no network. Bash's
          built-in read-only commands (ls, cat, ...) run without approval, so
          the sandbox denies reading your whole home directory, re-allowing
          only the Python installation the workspace venv points to.
  Both: --strict-mcp-config (no MCP servers); file-tool deny rules on your
  home directory and the repository; extra known side-effect tools listed in
  --disallowedTools as a second layer; --max-turns.
  Dedicated profile (v0.5): every Claude run uses CLAUDE_CONFIG_DIR pointed at
  an empty study profile (default ~/.claude-written-init, logged in once with
  your subscription), so your plugins, hooks, mods, global CLAUDE.md, skills
  and settings never load. A user plugin's SessionStart hook injected ~2.5 KB
  of instructions into the first real sample before this. disableAllHooks is
  set as a second layer, and any hook event or loaded plugin in the transcript
  is a fence violation.
  Request level (v0.8): the startup tool list omits server-side and deferred
  tools. 2.1.318 sent a deferred `advisor` server tool (a second model) with
  every request although startup reported only Read, Write, Edit. The advisor
  is disabled with CLAUDE_CODE_DISABLE_ADVISOR_TOOL=1, and after every run the
  CLI's own session log is copied (emails, account/org UUIDs and the home path
  redacted) and the tools its API
  requests carried must be exactly the designed set, with no server-tool blocks.
  With the advisor off, 2.1.318 still sent DeferredToolPlaceholder (deferred,
  "never call this tool"), which it adds while tool search is on (v0.9):
  ENABLE_TOOL_SEARCH=false turns tool search off, leaving only the inline tools.

Codex (`codex exec`)
  ro      read-only sandbox: no writes, no network. Codex cannot disable its
          shell, so commands CAN still run (read-only); the agent is told not
          to, and every command is flagged in the audit.
  tools   workspace-write sandbox: writes limited to the workspace and temp
          dirs, no network for commands.
  Both: web search disabled, --ignore-user-config, --ephemeral,
  --skip-git-repo-check, and CODEX_HOME pointed at a dedicated study profile
  (default ~/.codex-written-init, logged in once) so a global AGENTS.md,
  skills or config can't load either.
  Not covered: Codex sandboxes restrict writes and network, not reads. The
  agent could read files elsewhere on disk if it went looking; the transcript
  audit flags any path outside the workspace.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

# The exact tool set each Claude Code condition gets (passed with --tools and
# verified against the startup tool list on every run).
EXPECTED_TOOLS = {
    ("claude", "noexec"): ["Read", "Write", "Edit"],
    ("claude", "tools"): ["Read", "Write", "Edit", "Bash"],
}
# Second layer only: --tools is what restricts. Includes the side-effect tools
# the v0.3 check found available in Claude Code 2.1.318.
CLAUDE_ALWAYS_DISALLOWED = [
    "WebSearch", "WebFetch", "Task", "Agent", "NotebookEdit", "Glob", "Grep",
    "CronCreate", "CronDelete", "CronList", "ScheduleWakeup", "SendMessage", "PushNotification",
    "PublishPlugin", "ShareOnboardingGuide", "DesignSync", "Skill", "Workflow", "ListAgents",
    "TaskStop", "ToolSearch", "EnterWorktree", "ExitWorktree", "ReportFindings",
]
PYTHON_RULE = "Bash(.venv/bin/python *)"


# Plugins built into Claude Code itself, observed in a clean study profile with Claude Code
# 2.1.318 (isolation check 2026-11-04, results/isolation/claude_noexec_20261104_044223). They
# ship with every copy of the CLI, like its system prompt, so they are part of the stock
# harness being studied, not user configuration. Exact names only: a prefix rule would let
# any plugin named cc-plugin-* through. A new name (including a new built-in after a CLI
# update) is a violation until reviewed and added here with a DECISIONS.md entry.
BUILTIN_PLUGINS = frozenset({
    "cc-plugin-sec-default",
    "cc-plugin-agents-md",
    "cc-plugin-telemetry",
    "cc-plugin-privacy",
    "cc-plugin-plugin-authoring",
})


def unexpected_plugins(plugins: list | None) -> list[str]:
    return sorted(str(p) for p in (plugins or []) if str(p) not in BUILTIN_PLUGINS)


def startup_tools_violation(agent: str, condition: str, available_tools: list[str] | None) -> str | None:
    """The tool list Claude Code reports at startup (v0.4). Fail-closed if it reports none."""
    expected = EXPECTED_TOOLS.get((agent, condition))
    if expected is None:  # Codex reports no tool list; its fence is the sandbox mode + profile
        return None
    if available_tools is None:
        return "Claude Code did not report its tool list, so the fence could not be verified"
    extra = sorted(set(available_tools) - set(expected))
    return f"unexpected tools available: {', '.join(extra)}" if extra else None


def request_violation(agent: str, condition: str, request_tools: list[str] | None,
                      server_blocks: list[str] | None) -> str | None:
    """The tools the API requests actually carried, from the CLI's session log (v0.8).
    Fail-closed: no log, or a log we can't read, counts as a violation."""
    expected = EXPECTED_TOOLS.get((agent, condition))
    if expected is None:
        return None
    if server_blocks:
        return f"server-side tool blocks in the session: {', '.join(sorted(set(server_blocks)))}"
    if request_tools is None:
        return ("Claude Code's session log was missing or unreadable, so the tools its API requests "
                "carried could not be verified")
    extra = sorted(set(request_tools) - set(expected))
    return f"API requests carried tools beyond the designed set: {', '.join(extra)}" if extra else None


def fence_violation(agent: str, condition: str, available_tools: list[str] | None,
                    hook_events: list | None = None, plugins: list | None = None,
                    skills: list | None = None, request_tools: list[str] | None = None,
                    server_blocks: list[str] | None = None) -> str | None:
    """None if the session ran inside the designed fence, else a reason. Fail-closed:
    a Claude run that reports no tool list, or whose session log can't be checked, counts as
    a violation. Any hook firing or plugin loading means context we didn't write reached the agent."""
    if hook_events:
        names = sorted({str(h.get("hook_name") or h.get("hook_event_name") or h.get("subtype") or "hook")
                        for h in hook_events if isinstance(h, dict)})
        return f"hooks ran in the agent session ({', '.join(names) or 'unnamed'})"
    synced = sorted(str(x) for x in (skills or []) if str(x).startswith("anthropic-skills:"))
    if synced:  # the namespace Claude Code reserves for skills synced from claude.ai
        return f"account-synced skills loaded in the agent session: {', '.join(synced[:5])}"
    extra_plugins = unexpected_plugins(plugins)
    if extra_plugins:
        return f"non-built-in plugins loaded in the agent session: {', '.join(extra_plugins)}"
    return (startup_tools_violation(agent, condition, available_tools)
            or request_violation(agent, condition, request_tools, server_blocks))


# ---- dedicated study profiles ----------------------------------------------------

PROFILE_ENV = {"claude": "CLAUDE_CONFIG_DIR", "codex": "CODEX_HOME"}
PROFILE_OVERRIDE = {"claude": "WRITTEN_INIT_CLAUDE_PROFILE", "codex": "WRITTEN_INIT_CODEX_PROFILE"}
PROFILE_DEFAULT = {"claude": ".claude-written-init", "codex": ".codex-written-init"}
# Removed from the agent's environment: an API key would silently switch billing away from
# the subscription login, and a preset config dir would bypass the study profile.
STRIPPED_ENV = ["ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN",
                "OPENAI_API_KEY", "CODEX_API_KEY", "CLAUDE_CONFIG_DIR", "CODEX_HOME"]


# Settings the Claude study profile must carry (user scope, where Claude Code documents the
# sync opt-outs). Account sync otherwise downloads your claude.ai skills and plugins into
# every profile you log into: found in the study profile on 2026-11-04 (v0.7).
REQUIRED_CLAUDE_PROFILE_SETTINGS = {
    "disableAllHooks": True,
    "syncClaudeAiSkills": False,
    "syncClaudeAiPlugins": False,
}
# Env vars for the advisor (a server-side second model, v0.8) and tool search (v0.9). agent_env
# turns both off; a profile env block that sets any of them would make the run depend on
# profile state, so it is refused.
FENCE_ENV = frozenset({"CLAUDE_CODE_DISABLE_ADVISOR_TOOL", "CLAUDE_CODE_ENABLE_EXPERIMENTAL_ADVISOR_TOOL",
                       "ENABLE_TOOL_SEARCH"})


def _real_files(root: Path) -> list[Path]:
    """Files under root that count as content: skips sync bookkeeping (dotfiles) and .trash/."""
    if not root.is_dir():
        return []
    return [f for f in root.rglob("*") if f.is_file() and not f.name.startswith(".")
            and ".trash" not in f.relative_to(root).parts]


def profile_dir(agent: str) -> Path:
    override = os.environ.get(PROFILE_OVERRIDE[agent])
    return Path(override).expanduser() if override else Path.home() / PROFILE_DEFAULT[agent]


def setup_hint(agent: str) -> str:
    d = profile_dir(agent)
    login = "claude auth login" if agent == "claude" else "codex login"
    return (f"one-time setup:  mkdir -p {d} && {PROFILE_ENV[agent]}={d} {login}\n"
            f"(or: uv run python scripts/setup_profiles.py --agent {agent})")


def check_profile(agent: str) -> Path:
    """Refuse to run unless the study profile exists and carries no extensions."""
    d = profile_dir(agent)
    if not d.is_dir():
        raise RuntimeError(f"{agent} study profile {d} does not exist.\n{setup_hint(agent)}")
    problems = []
    if agent == "claude":
        main = d / "settings.json"
        cfg = {}
        if main.exists():
            try:
                cfg = json.loads(main.read_text() or "{}")
            except json.JSONDecodeError:
                problems.append(f"{main} is not valid JSON")
        for k, v in REQUIRED_CLAUDE_PROFILE_SETTINGS.items():
            if cfg.get(k) != v:
                problems.append(f"{main} must set \"{k}\": {json.dumps(v)} (rerun setup_profiles.py)")
        for name in ("settings.json", "settings.local.json"):
            f = d / name
            if f.exists():
                try:
                    c = json.loads(f.read_text() or "{}")
                except json.JSONDecodeError:
                    continue
                if c.get("hooks"):
                    problems.append(f"{f} defines hooks")
                if any(c.get("enabledPlugins", {}).values()):
                    problems.append(f"{f} enables plugins")
                if "advisorModel" in c:
                    problems.append(f"{f} sets advisorModel")
                env_block = c.get("env") if isinstance(c.get("env"), dict) else {}
                touched = sorted(FENCE_ENV & set(env_block))
                if touched:
                    problems.append(f"{f} sets {', '.join(touched)} in its env block")
        # Account-synced content: bookkeeping dotfiles and .trash/ are fine; anything else means
        # sync is still delivering skills/plugins. (plugins/store holds built-in usage counters.)
        for p in (d / "skills" / "synced", d / "plugins" / "synced"):
            files = _real_files(p)
            if files:
                problems.append(f"{p} holds {len(files)} synced file(s), e.g. {files[0].relative_to(d)}"
                                " (rerun setup_profiles.py)")
        for sub in ("skills", "agents", "commands", "hooks", "output-styles", "rules"):
            p = d / sub
            files = [f for f in _real_files(p) if "synced" not in f.relative_to(p).parts]
            if files:
                problems.append(f"{p} is not empty, e.g. {files[0].relative_to(d)}")
        if (d / "CLAUDE.md").exists() and (d / "CLAUDE.md").read_text().strip():
            problems.append(f"{d / 'CLAUDE.md'} is not empty")
    else:
        if (d / "AGENTS.md").exists() and (d / "AGENTS.md").read_text().strip():
            problems.append(f"{d / 'AGENTS.md'} is not empty")
        for sub in ("skills", "prompts", "rules"):
            p = d / sub
            if p.is_dir() and any(x for x in p.rglob("*") if x.is_file()):
                problems.append(f"{p} is not empty")
    if problems:
        raise RuntimeError(f"{agent} study profile {d} must stay empty apart from the login:\n  - "
                           + "\n  - ".join(problems))
    return d


def agent_env(agent: str) -> tuple[dict, list[str]]:
    """Environment for the agent process: study profile on, keys and overrides off."""
    env = {k: v for k, v in os.environ.items() if k not in STRIPPED_ENV}
    stripped = [k for k in STRIPPED_ENV if k in os.environ and k not in PROFILE_ENV.values()]
    env[PROFILE_ENV[agent]] = str(check_profile(agent))
    if agent == "claude":
        env["DISABLE_AUTOUPDATER"] = "1"  # keep the CLI version fixed within a run
        env["CLAUDE_CODE_DISABLE_ADVISOR_TOOL"] = "1"  # no server-side second model (v0.8)
        env["ENABLE_TOOL_SEARCH"] = "false"  # no DeferredToolPlaceholder, only inline tools (v0.9)
    return env, stripped


_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
# The only keys 2.1.318 writes the account/org ids under (all 123 occurrences in the v0.8 backfill).
_ID_KEYS = ("accountUuid", "organizationUuid")


def _map_strings(obj, fn):
    if isinstance(obj, str):
        return fn(obj)
    if isinstance(obj, list):
        return [_map_strings(x, fn) for x in obj]
    if isinstance(obj, dict):
        return {k: _map_strings(v, fn) for k, v in obj.items()}
    return obj


def _account_ids(obj) -> set[str]:
    if isinstance(obj, list):
        return {i for x in obj for i in _account_ids(x)}
    if not isinstance(obj, dict):
        return set()
    own = {v for k, v in obj.items() if k in _ID_KEYS and isinstance(v, str) and v}
    return own | {i for v in obj.values() for i in _account_ids(v)}


def redact_log(text: str, home: str | None = None) -> str:
    """Redact emails, account/org UUIDs (found by key, then replaced wherever they occur) and the
    home path (-> ~). Works on each line's decoded JSON, so escapes like \\n next to a match can't
    break; a line that isn't JSON is redacted as plain text. Session and message uuids are kept."""
    lines = text.splitlines()
    rows = []
    for line in lines:
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            rows.append(None)
    ids = sorted(_account_ids([r for r in rows if r is not None]), key=len, reverse=True)
    home = home or str(Path.home())
    home_re = re.compile(re.escape(home) + r"(?![A-Za-z0-9._-])") if home not in ("", "/") else None

    def scrub(s: str) -> str:
        s = _EMAIL.sub("<redacted-email>", s)
        for i in ids:
            s = s.replace(i, "<redacted-uuid>")
        return home_re.sub("~", s) if home_re else s

    out = [scrub(line) if r is None else json.dumps(_map_strings(r, scrub), ensure_ascii=False)
           for r, line in zip(rows, lines)]
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")


def save_session_log(profile: Path, session_id: str | None, dest: Path) -> Path | None:
    """Copy Claude Code's own log of this session (profile/projects/<cwd>/<id>.jsonl) to dest,
    redacted. None if there is no single match: the fence check then fails closed."""
    if not session_id:
        return None
    found = list((profile / "projects").glob(f"*/{session_id}.jsonl"))
    if len(found) != 1:
        return None
    dest.write_text(redact_log(found[0].read_text(errors="replace")))
    return dest


@dataclass
class AgentRun:
    cmd: list[str]
    profile: str
    stripped_env: list[str]
    returncode: int | None
    timed_out: bool
    seconds: float
    transcript: Path
    stderr: Path
    final_text: str
    session_log: Path | None = None  # Claude only: redacted copy of the CLI's session log


def cli_version(agent: str) -> str:
    exe = shutil.which(agent)
    if exe is None:
        return "not installed"
    try:
        env = {k: v for k, v in os.environ.items() if k not in STRIPPED_ENV}
        return subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=30,
                              env=env).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"


def python_base(workspace: Path) -> Path | None:
    """The base Python installation the workspace venv runs on (it must stay readable)."""
    py = workspace / ".venv" / "bin" / "python"
    if not py.exists():
        return None
    out = subprocess.run([str(py), "-c", "import sys; print(sys.base_prefix)"], capture_output=True,
                         text=True, timeout=60)
    return Path(out.stdout.strip()).resolve() if out.returncode == 0 and out.stdout.strip() else None


def claude_settings(repo_root: Path, workspace: Path | None = None, py_base: Path | None = None) -> dict:
    home = Path.home().resolve()
    r = str(repo_root.resolve())
    if workspace is not None:
        ws = workspace.resolve()
        if ws == home or home in ws.parents:
            raise RuntimeError(f"agent workspace {ws} is inside your home directory, which the fence "
                               "denies; point TMPDIR somewhere outside it")
    deny = []
    for path in dict.fromkeys([str(home), r]):  # home first; repo too in case it lives elsewhere
        deny += [f"Read(/{path}/**)", f"Edit(/{path}/**)", f"Write(/{path}/**)"]
    allow_read = [str(py_base)] if py_base is not None and (py_base == home or home in py_base.parents) else []
    fs = {"denyRead": list(dict.fromkeys([str(home), r]))}
    if allow_read:
        fs["allowRead"] = allow_read
    return {
        "disableAllHooks": True,
        "permissions": {"deny": deny + ["WebFetch", "WebSearch"]},
        "sandbox": {
            "enabled": True,
            "failIfUnavailable": True,
            "allowUnsandboxedCommands": False,
            "autoAllowBashIfSandboxed": False,
            "filesystem": fs,
            "network": {"allowedDomains": []},
        },
    }


def claude_cmd(prompt: str, model: str, condition: str, settings_path: Path, max_turns: int) -> list[str]:
    if ("claude", condition) not in EXPECTED_TOOLS:
        raise ValueError(f"claude has no condition {condition!r}")
    tools = EXPECTED_TOOLS[("claude", condition)]
    allowed = ["Read", "Write", "Edit"] + ([PYTHON_RULE] if condition == "tools" else [])
    disallowed = list(CLAUDE_ALWAYS_DISALLOWED) + (["Bash"] if condition == "noexec" else [])
    return [
        "claude", "-p", prompt,
        "--model", model,
        "--output-format", "stream-json", "--verbose",
        "--max-turns", str(max_turns),
        "--settings", str(settings_path),
        "--strict-mcp-config",
        "--tools", ",".join(tools),
        "--allowedTools", ",".join(allowed),
        "--disallowedTools", ",".join(disallowed),
    ]


def codex_cmd(model: str, condition: str, workspace: Path, last_message: Path) -> list[str]:
    sandbox = {"ro": "read-only", "tools": "workspace-write"}.get(condition)
    if sandbox is None:
        raise ValueError(f"codex has no condition {condition!r}")
    return [
        "codex", "exec",
        "--json",
        "-o", str(last_message),
        "-C", str(workspace),
        "-m", model,
        "-s", sandbox,
        "-c", 'web_search="disabled"',
        "--skip-git-repo-check",
        "--ephemeral",
        "--ignore-user-config",
        "-",  # read the prompt from stdin
    ]


def run_agent(agent: str, condition: str, model: str, prompt: str, workspace: Path, out_dir: Path,
              repo_root: Path, tag: str, max_turns: int = 40, timeout_s: int = 1800) -> AgentRun:
    """Run one headless agent session. Transcript and stderr go to out_dir/<tag>.*"""
    transcript = out_dir / f"{tag}.transcript.jsonl"
    stderr = out_dir / f"{tag}.stderr.log"
    stdin_text = None
    if agent == "claude":
        settings = out_dir / "claude_settings.json"
        settings.write_text(json.dumps(claude_settings(repo_root, workspace, python_base(workspace)), indent=2))
        cmd = claude_cmd(prompt, model, condition, settings, max_turns)
    elif agent == "codex":
        last = out_dir / f"{tag}.final.md"
        cmd = codex_cmd(model, condition, workspace, last)
        stdin_text = prompt
    else:
        raise ValueError(f"unknown agent {agent!r}")

    env, stripped = agent_env(agent)
    t0 = time.time()
    timed_out = False
    with open(transcript, "w") as out, open(stderr, "w") as err:
        proc = subprocess.Popen(cmd, cwd=workspace, stdout=out, stderr=err, env=env,
                                stdin=subprocess.PIPE if stdin_text is not None else subprocess.DEVNULL,
                                text=True)
        try:
            proc.communicate(input=stdin_text, timeout=timeout_s)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            timed_out = True

    final_text, session_log = "", None
    if agent == "codex":
        last = out_dir / f"{tag}.final.md"
        if last.exists():
            final_text = last.read_text()
    else:
        from .transcript import parse

        p = parse("claude", transcript, workspace)
        final_text = p["final_text"] or ""
        session_log = save_session_log(Path(env[PROFILE_ENV[agent]]), p["session_id"],
                                       out_dir / f"{tag}.session.jsonl")
    return AgentRun(cmd=cmd, profile=env[PROFILE_ENV[agent]], stripped_env=stripped,
                    returncode=proc.returncode, timed_out=timed_out,
                    seconds=round(time.time() - t0, 1), transcript=transcript, stderr=stderr,
                    final_text=final_text, session_log=session_log)


def redact_cmd(cmd: list[str]) -> list[str]:
    """For meta.json: replace the long prompt argument with a placeholder."""
    out = list(cmd)
    if out[:2] == ["claude", "-p"]:
        out[2] = "<prompt.md>"
    return out
