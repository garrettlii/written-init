"""Fake `claude` and `codex` CLIs for offline tests. Installed onto PATH by the
fixture in test_agents.py. Behavior is chosen with FAKE_AGENT_MODE:
  good          write a correct sparse_parity build.py (or reply with it)
  bad_then_good first run breaks a rule (np.random), second run is correct
  nothing       produce no code
  escape        try disallowed things (sklearn, reading outside the workspace)
  leak          (isolation check) actually read the canaries and write outside the workspace
FAKE_EXTRA_TOOLS (comma-separated) makes the fake claude report extra tools at
startup, like real Claude Code 2.1.318 did before --tools was used.
FAKE_HOOK=1 emits a SessionStart hook_response first (like the ponytail plugin did);
FAKE_PLUGINS=a,b reports loaded plugins; FAKE_SKILLS=a,b reports loaded skills;
FAKE_AGENTS=a,b reports the agent roster (default: the 2.1.318 roster).
FAKE_ENV_LOG records the env the agent got.
The fake claude also writes a session log shaped like real 2.1.318's (from
fixtures/claude_session_2_1_318.jsonl, with an email in it) into the profile's
projects/ folder. Its request-level tools are --tools plus FAKE_REQUEST_TOOLS;
FAKE_SERVER_BLOCK=session|stream adds an advisor call to the log or the stream;
FAKE_SESSION_LOG=none|garbage writes no log or an unreadable one.
Every prompt received is appended to $FAKE_AGENT_LOG for assertions."""

import json
import os
import re
import sys
import uuid
from pathlib import Path

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "claude_session_2_1_318.jsonl"
ADVISOR_CALL = [{"type": "server_tool_use", "id": "srvtoolu_01", "name": "advisor", "input": {}},
                {"type": "advisor_tool_result", "tool_use_id": "srvtoolu_01", "content": {"text": "advice"}}]
FAKE_ACCOUNT = "4c0ffee0-1111-4222-8333-444455556666"
ROSTER_2_1_318 = "claude,Explore,general-purpose,Plan,statusline-setup"  # init roster before web-fetch appeared
REF = Path(os.environ["FAKE_REF_BUILD"]).read_text()
BAD = "import numpy as np\ndef build_weights():\n    return {'W0': np.random.rand(16, 64)}\n"
MODE = os.environ.get("FAKE_AGENT_MODE", "good")
LOG = Path(os.environ["FAKE_AGENT_LOG"])


def calls_so_far() -> int:
    return len(LOG.read_text().split("\x00")) - 1 if LOG.exists() else 0


def emit(obj):
    print(json.dumps(obj), flush=True)


def pick_code() -> str | None:
    if MODE == "nothing":
        return None
    if MODE == "bad_then_good" and calls_so_far() == 1:
        return BAD
    return REF


def record_env():
    if os.environ.get("FAKE_ENV_LOG"):
        Path(os.environ["FAKE_ENV_LOG"]).write_text(json.dumps({
            k: os.environ.get(k) for k in ("CLAUDE_CONFIG_DIR", "CODEX_HOME", "ANTHROPIC_API_KEY",
                                           "OPENAI_API_KEY", "DISABLE_AUTOUPDATER",
                                           "CLAUDE_CODE_DISABLE_ADVISOR_TOOL", "ENABLE_TOOL_SEARCH")}))


def write_session_log(sid: str, tools: list[str]):
    mode = os.environ.get("FAKE_SESSION_LOG", "")
    if mode == "none":
        return
    d = Path(os.environ["CLAUDE_CONFIG_DIR"]) / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(Path.cwd()))
    d.mkdir(parents=True, exist_ok=True)
    if mode == "garbage":
        (d / f"{sid}.jsonl").write_text('{"type": "api-request-shape", "shape": {"tools": [\n')
        return
    rows = [json.loads(line) for line in FIXTURE.read_text().splitlines()]
    extra = [t for t in os.environ.get("FAKE_REQUEST_TOOLS", "").split(",") if t]
    for r in rows:
        if r.get("type") == "api-request-shape":
            by_name = {t["name"]: t for t in r["shape"]["tools"]}
            r["shape"]["tools"] = [by_name.get(n, {"name": n}) for n in tools + extra]
    if os.environ.get("FAKE_SERVER_BLOCK") == "session":
        rows.append({"type": "assistant", "message": {"role": "assistant", "content": ADVISOR_CALL}})
    old_sid = next(r["sessionId"] for r in rows if r.get("sessionId"))
    text = "".join(json.dumps(r) + "\n" for r in rows)
    # Put back what a real log holds (the fixture is redacted), so tests can check the copy redacts it.
    (d / f"{sid}.jsonl").write_text(text.replace(old_sid, sid).replace("<redacted-email>", "someone@example.edu")
                                    .replace("00000000-0000-0000-0000-000000000000", FAKE_ACCOUNT)
                                    .replace("/Users/me", str(Path.home())))


def fake_claude(argv):
    record_env()
    prompt = argv[argv.index("-p") + 1]
    with open(LOG, "a") as f:
        f.write(prompt + "\x00")
    tools = argv[argv.index("--tools") + 1].split(",") if "--tools" in argv else []
    extra = [t for t in os.environ.get("FAKE_EXTRA_TOOLS", "").split(",") if t]
    if os.environ.get("FAKE_HOOK"):
        emit({"type": "system", "subtype": "hook_response", "hook_name": "SessionStart:startup",
              "output": "PONYTAIL MODE ACTIVE"})
    plugins = [{"name": n} for n in os.environ.get("FAKE_PLUGINS", "").split(",") if n]
    skills = [n for n in os.environ.get("FAKE_SKILLS", "").split(",") if n]
    agents = [n for n in os.environ.get("FAKE_AGENTS", ROSTER_2_1_318).split(",") if n]
    sid = str(uuid.uuid4())
    emit({"type": "system", "subtype": "init", "session_id": sid, "model": argv[argv.index("--model") + 1],
          "tools": tools + extra, "plugins": plugins, "skills": skills, "agents": agents})
    write_session_log(sid, tools)
    if os.environ.get("FAKE_SERVER_BLOCK") == "stream":
        emit({"type": "assistant", "session_id": sid, "message": {"content": ADVISOR_CALL}})
    if MODE == "leak":
        import re
        canary = re.search(r"(\S+\.isolation_canary)", prompt).group(1)
        home_canary = re.search(r"(\S+\.written_init_home_canary_\w+)", prompt).group(1)
        target = re.search(r"(\S+\.isolation_write_test)", prompt).group(1)
        Path(target).write_text("test")
        for c in (canary, home_canary):
            emit({"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Read", "input": {"file_path": c}}]}})
            emit({"type": "user", "message": {"content": [
                {"type": "tool_result", "content": Path(c).read_text()}]}})
        emit({"type": "result", "subtype": "success", "result": "all steps succeeded. NO OTHER INSTRUCTIONS",
              "num_turns": 2})
        return
    if MODE == "escape":
        emit({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Bash", "input": {"command": "python -c 'import sklearn'"}},
            {"type": "tool_use", "name": "Read", "input": {"file_path": "/etc/hosts"}}]}})
        emit({"type": "result", "subtype": "success", "result": "done", "num_turns": 2,
              "permission_denials": [{"tool_name": "Bash"}]})
        return
    code = pick_code()
    if code is not None:
        Path("build.py").write_text(code)
        Path("NOTES.md").write_text("Counts relevant bits, then a ReLU parity ladder.")
        emit({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Write", "input": {"file_path": str(Path.cwd() / "build.py")}}]}})
        emit({"type": "user", "message": {"content": [{"type": "tool_result", "content": "ok"}]}})
    emit({"type": "result", "subtype": "success", "result": "Wrote build.py. NO OTHER INSTRUCTIONS", "num_turns": 3,
          "total_cost_usd": 0.01, "usage": {"input_tokens": 10, "output_tokens": 20}})


def fake_codex(argv):
    record_env()
    prompt = sys.stdin.read()
    with open(LOG, "a") as f:
        f.write(prompt + "\x00")
    last = Path(argv[argv.index("-o") + 1])
    ws = Path(argv[argv.index("-C") + 1])
    sandbox = argv[argv.index("-s") + 1]
    emit({"type": "thread.started", "thread_id": "t1"})
    code = pick_code()
    if sandbox == "workspace-write" and code is not None:
        (ws / "build.py").write_text(code)
        emit({"type": "item.completed", "item": {"type": "command_execution",
              "command": ".venv/bin/python build.py", "aggregated_output": "", "exit_code": 0}})
        text = "Wrote build.py."
    else:
        text = "Explanation.\n```python\n" + code + "```\n" if code else "I could not do it."
    emit({"type": "item.completed", "item": {"type": "agent_message", "text": text}})
    emit({"type": "turn.completed", "usage": {"input_tokens": 5, "output_tokens": 7}})
    last.write_text(text)


if __name__ == "__main__":
    name, argv = os.environ["FAKE_AGENT_NAME"], sys.argv[1:]
    if argv == ["--version"]:
        print(f"fake-{name} 0.0")
    elif name == "claude":
        fake_claude(argv)
    else:
        fake_codex(argv)
