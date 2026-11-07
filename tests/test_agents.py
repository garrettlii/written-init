"""Offline tests of the headless-agent pipeline, using fake CLIs on PATH."""

import json
import os
import stat
import sys
from pathlib import Path

import pytest

import written_init.agents.generate as gen
from written_init.agents import CONDITIONS
from written_init.agents.runners import (BUILTIN_PLUGINS, EXPECTED_TOOLS, PYTHON_RULE,
                                        REQUIRED_CLAUDE_PROFILE_SETTINGS, check_profile, claude_cmd,
                                        claude_settings, codex_cmd, fence_violation, redact_log,
                                        request_violation)
from written_init.agents.transcript import flags, latest_isolation_roster, parse, parse_session, roster_flag
from written_init.paths import INITS, ROOT

HERE = Path(__file__).resolve().parent
REF = INITS / "sparse_parity" / "reference" / "sample_00" / "build.py"
ROSTER = ["claude", "Explore", "general-purpose", "Plan", "statusline-setup"]  # fake CLI default


def _write_report(iso: Path, name: str, condition: str, leaks: list, agents, agent: str = "claude") -> None:
    (iso / name).mkdir(parents=True)
    report = {"agent": agent, "condition": condition, "unexpected_leaks": leaks}
    if agents is not None:
        report["agents"] = agents
    (iso / name / "report.json").write_text(json.dumps(report))


@pytest.fixture
def fake_env(tmp_path, monkeypatch):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    for name in ("claude", "codex"):
        exe = bindir / name
        exe.write_text(f"#!{sys.executable}\nimport os, runpy\nos.environ['FAKE_AGENT_NAME'] = {name!r}\n"
                       f"runpy.run_path({str(HERE / 'fake_agents.py')!r}, run_name='__main__')\n")
        exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{bindir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_REF_BUILD", str(REF))
    monkeypatch.setenv("FAKE_AGENT_LOG", str(tmp_path / "prompts.log"))
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    for agent in ("claude", "codex"):  # empty study profiles, as setup_profiles.py makes them
        (tmp_path / f"profile_{agent}").mkdir()
        monkeypatch.setenv(f"WRITTEN_INIT_{agent.upper()}_PROFILE", str(tmp_path / f"profile_{agent}"))
    (tmp_path / "profile_claude" / "settings.json").write_text(json.dumps(REQUIRED_CLAUDE_PROFILE_SETTINGS))
    monkeypatch.setenv("FAKE_ENV_LOG", str(tmp_path / "env.json"))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-should-be-stripped")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-should-be-stripped")
    monkeypatch.setattr(gen, "INITS", tmp_path / "inits")
    for cond in CONDITIONS["claude"]:  # passing isolation reports with the fake CLI's default roster
        _write_report(tmp_path / "iso_ref", f"claude_{cond}_20260101_000000", cond, [], ROSTER)
    monkeypatch.setattr(gen, "ISOLATION", tmp_path / "iso_ref")
    real = gen.make_workspace
    monkeypatch.setattr(gen, "make_workspace", lambda writable, with_python: real(writable, False))
    return tmp_path


def _meta(d):
    return json.loads((d / "meta.json").read_text())


@pytest.mark.parametrize("agent,condition", [(a, c) for a, cs in CONDITIONS.items() for c in cs])
def test_every_condition_end_to_end(fake_env, monkeypatch, agent, condition):
    monkeypatch.setenv("FAKE_AGENT_MODE", "good")
    d = gen.generate_one("sparse_parity", agent, "m1", condition)
    m = _meta(d)
    assert m["status"] == "ok", m["final_message"]
    assert (d / "weights.npz").exists() and (d / "attempt0.transcript.jsonl").exists()
    assert m["agent"] == agent and m["condition"] == condition and m["cli_version"].startswith("fake")
    assert m["audited"] is False
    assert d.parent.name == gen.source_name(agent, "m1", condition)


def test_retry_is_a_fresh_run_with_only_the_rule_error(fake_env, monkeypatch):
    monkeypatch.setenv("FAKE_AGENT_MODE", "bad_then_good")
    d = gen.generate_one("sparse_parity", "claude", "m1", "noexec", max_retries=1)
    m = _meta(d)
    assert m["status"] == "ok" and len(m["attempts"]) == 2 and not m["attempts"][0]["ok"]
    prompts = (fake_env / "prompts.log").read_text().split("\x00")[:-1]
    assert "A previous attempt" not in prompts[0]
    assert "A previous attempt" in prompts[1] and ".random" in prompts[1]
    assert "accuracy" not in prompts[1].split("A previous attempt")[1].lower()


def test_failure_leaves_no_weights(fake_env, monkeypatch):
    monkeypatch.setenv("FAKE_AGENT_MODE", "nothing")
    d = gen.generate_one("sparse_parity", "codex", "m1", "ro", max_retries=0)
    assert _meta(d)["status"] == "failed" and not (d / "weights.npz").exists()


def test_escape_attempts_are_flagged(fake_env, monkeypatch):
    monkeypatch.setenv("FAKE_AGENT_MODE", "escape")
    d = gen.generate_one("sparse_parity", "claude", "m1", "noexec", max_retries=0)
    msgs = " | ".join(f["message"] for f in _meta(d)["transcript_flags"] if f["severity"] == "red")
    assert "sklearn" in msgs and "outside the workspace" in msgs
    assert "permission denial" in msgs and "noexec" in msgs


def test_prompts_mention_only_their_condition():
    from written_init.agents.prompts import task_prompt
    from written_init.tasks import get_task
    t = get_task("gridnav")
    assert ".venv/bin/python" in task_prompt(t, "claude", "tools")
    assert ".venv/bin/python" not in task_prompt(t, "claude", "noexec")
    assert "build.py` in this folder" in task_prompt(t, "codex", "tools")
    assert "```python code block" in task_prompt(t, "codex", "ro")


# ---- the fence itself: these tests are the spec for runners.py ------------------

def test_claude_noexec_fence():
    cmd = claude_cmd("p", "m", "noexec", Path("s.json"), 10)
    # --tools is what restricts the set; --allowedTools only pre-approves (v0.4 lesson)
    assert cmd[cmd.index("--tools") + 1].split(",") == ["Read", "Write", "Edit"]
    assert cmd[cmd.index("--allowedTools") + 1].split(",") == ["Read", "Write", "Edit"]
    denied = set(cmd[cmd.index("--disallowedTools") + 1].split(","))
    assert {"Bash", "WebSearch", "WebFetch", "Task", "PublishPlugin", "SendMessage", "CronCreate",
            "ScheduleWakeup", "Skill", "Workflow"} <= denied
    assert "--strict-mcp-config" in cmd and cmd[cmd.index("--max-turns") + 1] == "10"


def test_claude_tools_fence(tmp_path, monkeypatch):
    cmd = claude_cmd("p", "m", "tools", Path("s.json"), 10)
    assert cmd[cmd.index("--tools") + 1].split(",") == ["Read", "Write", "Edit", "Bash"]
    allowed = cmd[cmd.index("--allowedTools") + 1].split(",")
    denied = cmd[cmd.index("--disallowedTools") + 1].split(",")
    assert PYTHON_RULE in allowed and "Bash" not in allowed and "Bash" not in denied
    home = tmp_path / "home"
    (home / ".uvpython").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    s = claude_settings(ROOT, py_base=home / ".uvpython")
    sb = s["sandbox"]
    assert sb["enabled"] and sb["failIfUnavailable"] and sb["network"]["allowedDomains"] == []
    assert sb["autoAllowBashIfSandboxed"] is False and sb["allowUnsandboxedCommands"] is False
    # Bash's auto-run read-only commands can't read the home directory, except the Python install
    assert str(home.resolve()) in sb["filesystem"]["denyRead"]
    assert sb["filesystem"]["allowRead"] == [str((home / ".uvpython").resolve())]
    assert f"Read(/{home.resolve()}/**)" in s["permissions"]["deny"]
    assert f"Read(/{ROOT.resolve()}/**)" in s["permissions"]["deny"]


def test_python_outside_home_needs_no_allow_rule(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    s = claude_settings(ROOT, py_base=Path("/usr"))
    assert "allowRead" not in s["sandbox"]["filesystem"]


def test_workspace_inside_home_is_refused(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    with pytest.raises(RuntimeError, match="TMPDIR"):
        claude_settings(ROOT, workspace=tmp_path / "ws")


@pytest.mark.parametrize("tools,ok", [
    (["Read", "Write", "Edit"], True),
    (["Edit", "Read", "Write"], True),                       # order doesn't matter
    (["Read", "Write", "Edit", "PublishPlugin"], False),     # what 2.1.318 actually did
    (["Read", "Write"], True),                               # fewer tools is still inside the fence
    (None, False),                                           # unverifiable -> fail closed
])
def test_fence_violation_rule(tools, ok):
    assert (fence_violation("claude", "noexec", tools, request_tools=["Read", "Write", "Edit"]) is None) == ok
    assert fence_violation("codex", "ro", tools) is None    # Codex reports no tool list


def test_extra_tools_stop_generation_and_keep_no_weights(fake_env, monkeypatch):
    monkeypatch.setenv("FAKE_AGENT_MODE", "good")
    monkeypatch.setenv("FAKE_EXTRA_TOOLS", "CronCreate,PublishPlugin")
    d = gen.generate_one("sparse_parity", "claude", "m1", "noexec", max_retries=2)
    m = _meta(d)
    assert m["status"] == "fence_violation" and len(m["attempts"]) == 1   # no retries burned
    assert not (d / "weights.npz").exists()
    assert "CronCreate" in m["final_message"] and "PublishPlugin" in m["final_message"]
    assert any("fence violation" in f["message"] for f in m["transcript_flags"])


@pytest.mark.parametrize("cond,mode", [("ro", "read-only"), ("tools", "workspace-write")])
def test_codex_fence(cond, mode):
    cmd = codex_cmd("m", cond, Path("/tmp/ws"), Path("/tmp/last.md"))
    assert cmd[cmd.index("-s") + 1] == mode
    assert 'web_search="disabled"' in cmd and "--ignore-user-config" in cmd and "--ephemeral" in cmd
    assert cmd[-1] == "-"


def test_codex_transcript_parsing(tmp_path):
    t = tmp_path / "t.jsonl"
    t.write_text("\n".join(json.dumps(e) for e in [
        {"type": "item.completed", "item": {"type": "command_execution", "command": "ls ~/", "exit_code": 0,
                                            "aggregated_output": "x"}},
        {"type": "item.completed", "item": {"type": "web_search", "query": "parity relu"}},
        {"type": "item.completed", "item": {"type": "agent_message", "text": "done"}},
        {"type": "turn.completed", "usage": {"input_tokens": 1}},
        "not json",
    ]))
    p = parse("codex", t)
    assert p["final_text"] == "done" and p["commands"] == ["ls ~/"] and len(p["web"]) == 1
    msgs = " | ".join(f["message"] for f in flags(p, "codex", "ro", tmp_path, ROOT))
    assert "web search" in msgs and "explored the filesystem" in msgs and "read-only command" in msgs


@pytest.mark.parametrize("mode,extra,expect_exit", [("good", "", 0), ("leak", "", 1), ("good", "CronCreate", 1)])
def test_isolation_check_detects_leaks(fake_env, mode, extra, expect_exit):
    """The isolation check must FAIL against an agent that really leaks or has extra tools."""
    import subprocess
    env = {**os.environ, "FAKE_AGENT_MODE": mode, "FAKE_EXTRA_TOOLS": extra, "PYTHONPATH": str(ROOT / "src")}
    proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "check_isolation.py"), "--agent", "claude",
                           "--model", "m", "--condition", "noexec", "--results-dir", str(fake_env / "iso")],
                          capture_output=True, text=True, env=env,
                          timeout=120)
    assert proc.returncode == expect_exit, proc.stdout + proc.stderr
    if mode == "leak":
        assert "read_repo_file             LEAK" in proc.stdout
        assert "read_home_file             LEAK" in proc.stdout
        assert "write_outside_workspace    LEAK" in proc.stdout
    if extra:
        assert "extra_tools                LEAK" in proc.stdout and "CronCreate" in proc.stdout
    assert not list(Path(os.environ["HOME"]).glob(".written_init_home_canary_*"))  # cleaned up
    assert not (ROOT / ".isolation_canary").exists() and not (ROOT / ".isolation_write_test").exists()
    assert list((fake_env / "iso").glob("*/report.json"))



# ---- v0.5: dedicated profiles, no hooks, no plugins ---------------------------------

@pytest.mark.parametrize("agent,condition,var", [("claude", "noexec", "CLAUDE_CONFIG_DIR"), ("codex", "ro", "CODEX_HOME")])
def test_agent_runs_in_study_profile_without_api_keys(fake_env, monkeypatch, agent, condition, var):
    monkeypatch.setenv("FAKE_AGENT_MODE", "good")
    d = gen.generate_one("sparse_parity", agent, "m1", condition)
    seen = json.loads((fake_env / "env.json").read_text())
    assert seen[var] == str(fake_env / f"profile_{agent}")
    assert seen["ANTHROPIC_API_KEY"] is None and seen["OPENAI_API_KEY"] is None
    m = _meta(d)
    assert m["profile"] == str(fake_env / f"profile_{agent}")
    assert set(m["stripped_env"]) == {"ANTHROPIC_API_KEY", "OPENAI_API_KEY"}
    if agent == "claude":
        assert seen["DISABLE_AUTOUPDATER"] == "1" and seen["CLAUDE_CODE_DISABLE_ADVISOR_TOOL"] == "1"
        assert seen["ENABLE_TOOL_SEARCH"] == "false"
        assert json.loads((d / "claude_settings.json").read_text())["disableAllHooks"] is True


@pytest.mark.parametrize("env_var,value,needle", [("FAKE_HOOK", "1", "hooks ran"),
                                                  ("FAKE_PLUGINS", "ponytail", "plugins loaded")])
def test_hooks_or_plugins_are_a_fence_violation(fake_env, monkeypatch, env_var, value, needle):
    """The first real sample was contaminated this way (ponytail SessionStart hook)."""
    monkeypatch.setenv("FAKE_AGENT_MODE", "good")
    monkeypatch.setenv(env_var, value)
    d = gen.generate_one("sparse_parity", "claude", "m1", "noexec", max_retries=2)
    m = _meta(d)
    assert m["status"] == "fence_violation" and needle in m["final_message"]
    assert len(m["attempts"]) == 1 and not (d / "weights.npz").exists()


def test_missing_profile_fails_before_any_sample_folder(fake_env, monkeypatch):
    monkeypatch.setenv("WRITTEN_INIT_CLAUDE_PROFILE", str(fake_env / "nope"))
    with pytest.raises(RuntimeError, match="setup_profiles.py"):
        gen.generate_one("sparse_parity", "claude", "m1", "noexec")
    assert not (fake_env / "inits").exists()


@pytest.mark.parametrize("make_dirty", [
    lambda d: (d / "settings.json").write_text(json.dumps({**REQUIRED_CLAUDE_PROFILE_SETTINGS,
                                                           "hooks": {"SessionStart": [{}]}})),
    lambda d: (d / "settings.json").write_text(json.dumps({**REQUIRED_CLAUDE_PROFILE_SETTINGS,
                                                           "enabledPlugins": {"ponytail@x": True}})),
    lambda d: ((d / "skills" / "s").mkdir(parents=True), (d / "skills" / "s" / "SKILL.md").write_text("x")),
    lambda d: (d / "CLAUDE.md").write_text("be lazy"),
    lambda d: (d / "settings.json").write_text(json.dumps({**REQUIRED_CLAUDE_PROFILE_SETTINGS,
                                                           "advisorModel": "claude-opus-5-5"})),
    lambda d: (d / "settings.json").write_text(json.dumps({**REQUIRED_CLAUDE_PROFILE_SETTINGS,
                                                           "env": {"CLAUDE_CODE_DISABLE_ADVISOR_TOOL": "0"}})),
    lambda d: (d / "settings.local.json").write_text(json.dumps(
        {"env": {"CLAUDE_CODE_ENABLE_EXPERIMENTAL_ADVISOR_TOOL": "1"}})),
    lambda d: (d / "settings.json").write_text(json.dumps({**REQUIRED_CLAUDE_PROFILE_SETTINGS,
                                                           "env": {"ENABLE_TOOL_SEARCH": "true"}})),
])
def test_dirty_claude_profile_is_refused(tmp_path, monkeypatch, make_dirty):
    d = tmp_path / "prof"
    d.mkdir()
    (d / "settings.json").write_text(json.dumps(REQUIRED_CLAUDE_PROFILE_SETTINGS))
    monkeypatch.setenv("WRITTEN_INIT_CLAUDE_PROFILE", str(d))
    check_profile("claude")  # clean: fine
    make_dirty(d)
    with pytest.raises(RuntimeError, match="must stay empty"):
        check_profile("claude")


def test_marketplace_metadata_alone_is_allowed(tmp_path, monkeypatch):
    d = tmp_path / "prof"
    (d / "plugins").mkdir(parents=True)
    (d / "plugins" / "known_marketplaces.json").write_text("{}")
    (d / "settings.json").write_text(json.dumps({**REQUIRED_CLAUDE_PROFILE_SETTINGS, "enabledPlugins": {}}))
    monkeypatch.setenv("WRITTEN_INIT_CLAUDE_PROFILE", str(d))
    check_profile("claude")


def test_isolation_check_fails_on_hooks(fake_env):
    import subprocess
    env = {**os.environ, "FAKE_AGENT_MODE": "good", "FAKE_HOOK": "1", "PYTHONPATH": str(ROOT / "src")}
    proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "check_isolation.py"), "--agent", "claude",
                           "--model", "m", "--condition", "noexec", "--results-dir", str(fake_env / "iso")],
                          capture_output=True, text=True, env=env, timeout=120)
    assert proc.returncode == 1 and "hooks_fired                LEAK" in proc.stdout



# ---- v0.6: built-in plugins are part of the stock harness ---------------------------

OBSERVED_2_1_318 = "cc-plugin-sec-default,cc-plugin-agents-md,cc-plugin-telemetry,cc-plugin-privacy,cc-plugin-plugin-authoring"


def test_builtin_plugins_observed_on_2_1_318_are_allowed(fake_env, monkeypatch):
    monkeypatch.setenv("FAKE_AGENT_MODE", "good")
    monkeypatch.setenv("FAKE_PLUGINS", OBSERVED_2_1_318)
    m = _meta(gen.generate_one("sparse_parity", "claude", "m1", "noexec"))
    assert m["status"] == "ok" and m["n_red_flags"] == 0
    assert set(m["attempts"][0]["plugins"]) == BUILTIN_PLUGINS


@pytest.mark.parametrize("plugins,bad", [
    (OBSERVED_2_1_318 + ",ponytail", "ponytail"),          # a user plugin alongside built-ins
    ("cc-plugin-lookalike", "cc-plugin-lookalike"),        # a prefix rule would have let this through
    ("cc-plugin-agents-md,cc-plugin-new-builtin", "cc-plugin-new-builtin"),  # new built-in after an update
])
def test_any_other_plugin_is_still_a_violation(fake_env, monkeypatch, plugins, bad):
    monkeypatch.setenv("FAKE_AGENT_MODE", "good")
    monkeypatch.setenv("FAKE_PLUGINS", plugins)
    m = _meta(gen.generate_one("sparse_parity", "claude", "m1", "noexec"))
    assert m["status"] == "fence_violation" and bad in m["final_message"]
    assert "cc-plugin-telemetry" not in m["final_message"]


def test_isolation_check_passes_with_builtins_only(fake_env):
    import subprocess
    env = {**os.environ, "FAKE_AGENT_MODE": "good", "FAKE_PLUGINS": OBSERVED_2_1_318,
           "PYTHONPATH": str(ROOT / "src")}
    proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "check_isolation.py"), "--agent", "claude",
                           "--model", "m", "--condition", "noexec", "--results-dir", str(fake_env / "iso")],
                          capture_output=True, text=True, env=env, timeout=120)
    assert proc.returncode == 0, proc.stdout
    assert "plugins_loaded             blocked" in proc.stdout and "built-in plugins (allowed)" in proc.stdout
    assert f"{'request_tools_exact':26s} blocked" in proc.stdout
    assert f"agent roster:             {ROSTER}" in proc.stdout
    (report,) = (fake_env / "iso").glob("*/report.json")
    assert json.loads(report.read_text())["agents"] == ROSTER


# ---- v1.1: agent roster is recorded; drift is a red flag, not a fence violation ------

def test_roster_drift_is_flagged_but_keeps_the_sample(fake_env, monkeypatch):
    monkeypatch.setenv("FAKE_AGENT_MODE", "good")
    m = _meta(gen.generate_one("sparse_parity", "claude", "m1", "noexec"))
    assert m["attempts"][0]["agents"] == ROSTER and m["n_red_flags"] == 0
    monkeypatch.setenv("FAKE_AGENTS", ",".join(ROSTER + ["web-fetch"]))
    d = gen.generate_one("sparse_parity", "claude", "m1", "noexec")
    m = _meta(d)
    assert m["status"] == "ok" and (d / "weights.npz").exists()
    (f,) = [f for f in m["transcript_flags"] if "agent roster" in f["message"]]
    assert f["severity"] == "red" and "added ['web-fetch'], removed []" in f["message"]
    assert "claude_noexec_20260101_000000" in f["message"]


def test_roster_reference_is_the_latest_passing_report(tmp_path):
    iso = tmp_path / "iso"
    _write_report(iso, "claude_noexec_20260101_000000", "noexec", [], ["a"])
    _write_report(iso, "claude_noexec_20260102_000000", "noexec", ["read_repo_file"], ["failing"])
    _write_report(iso, "claude_tools_20260103_000000", "tools", [], ["other-condition"])
    _write_report(iso, "codex_noexec_20260104_000000", "noexec", [], ["other-agent"], agent="codex")
    ref = latest_isolation_roster("claude", "noexec", iso)
    assert ref == {"report": str(iso / "claude_noexec_20260101_000000"), "agents": ["a"]}
    assert roster_flag(["a"], ref) is None
    assert "added ['b'], removed ['a']" in roster_flag(["b"], ref)["message"]
    _write_report(iso, "claude_noexec_20260105_000000", "noexec", [], None)  # pre-v1.1 report: no roster
    for r in (latest_isolation_roster("claude", "noexec", iso), latest_isolation_roster("claude", "ro", iso)):
        f = roster_flag(["a"], r)
        assert f["severity"] == "red" and "not compared" in f["message"]



# ---- v0.7: claude.ai skill/plugin sync is off and stays off --------------------------

SYNC = "22f9d993_17513e2d"  # shape of the org_user folder seen in the real profile


def _profile_like_garretts(root: Path) -> Path:
    """What the real study profile looked like on 2026-11-04 before v0.7."""
    d = root / "prof"
    (d / "skills" / "synced" / SYNC / "docx").mkdir(parents=True)
    (d / "skills" / "synced" / SYNC / "docx" / "SKILL.md").write_text("---\nname: docx\n---\n")
    (d / "skills" / "synced" / SYNC / ".last-complete-round").write_text("x")
    (d / "skills" / "synced" / f".bucket-{SYNC}").write_text("")
    (d / "plugins" / "synced" / SYNC).mkdir(parents=True)
    (d / "plugins" / "synced" / SYNC / ".marketplaces.json").write_text("{}")
    (d / "plugins" / "store").mkdir(parents=True)
    (d / "plugins" / "store" / "cc-plugin-agents-md_builtin-b049b47b3618.json").write_text("{}")
    (d / "settings.json").write_text(json.dumps({"disableAllHooks": True}))
    return d


@pytest.mark.parametrize("missing", sorted(REQUIRED_CLAUDE_PROFILE_SETTINGS))
def test_each_required_setting_is_enforced(tmp_path, monkeypatch, missing):
    d = tmp_path / "prof"
    d.mkdir()
    cfg = {k: v for k, v in REQUIRED_CLAUDE_PROFILE_SETTINGS.items() if k != missing}
    (d / "settings.json").write_text(json.dumps(cfg))
    monkeypatch.setenv("WRITTEN_INIT_CLAUDE_PROFILE", str(d))
    with pytest.raises(RuntimeError, match=missing):
        check_profile("claude")


def test_synced_skills_are_refused_until_migrated(tmp_path, monkeypatch):
    import subprocess
    d = _profile_like_garretts(tmp_path)
    monkeypatch.setenv("WRITTEN_INIT_CLAUDE_PROFILE", str(d))
    with pytest.raises(RuntimeError, match="synced file"):
        check_profile("claude")
    proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "setup_profiles.py"), "--agent", "claude",
                           "--no-login"], capture_output=True, text=True,
                          env={**os.environ, "PYTHONPATH": str(ROOT / "src")}, timeout=120)
    assert "profile ready" in proc.stdout, proc.stdout + proc.stderr
    check_profile("claude")  # now clean
    cfg = json.loads((d / "settings.json").read_text())
    assert cfg["syncClaudeAiSkills"] is False and cfg["syncClaudeAiPlugins"] is False and cfg["disableAllHooks"]
    trashed = list((d / "skills" / ".trash").rglob("SKILL.md"))
    assert len(trashed) == 1 and trashed[0].read_text().startswith("---")   # recoverable, not deleted
    assert (d / "plugins" / "store" / "cc-plugin-agents-md_builtin-b049b47b3618.json").exists()


def test_bookkeeping_and_trash_alone_are_fine(tmp_path, monkeypatch):
    d = tmp_path / "prof"
    (d / "skills" / "synced").mkdir(parents=True)
    (d / "skills" / "synced" / ".bucket-x").write_text("")
    (d / "skills" / ".trash" / "old" / "docx").mkdir(parents=True)
    (d / "skills" / ".trash" / "old" / "docx" / "SKILL.md").write_text("x")
    (d / "settings.json").write_text(json.dumps(REQUIRED_CLAUDE_PROFILE_SETTINGS))
    monkeypatch.setenv("WRITTEN_INIT_CLAUDE_PROFILE", str(d))
    check_profile("claude")


def test_synced_skills_loaded_at_runtime_are_a_violation(fake_env, monkeypatch):
    monkeypatch.setenv("FAKE_AGENT_MODE", "good")
    monkeypatch.setenv("FAKE_SKILLS", "anthropic-skills:docx,anthropic-skills:morning")
    m = _meta(gen.generate_one("sparse_parity", "claude", "m1", "noexec"))
    assert m["status"] == "fence_violation" and "account-synced skills" in m["final_message"]


def test_other_skill_names_are_recorded_not_blocked(fake_env, monkeypatch):
    monkeypatch.setenv("FAKE_AGENT_MODE", "good")
    monkeypatch.setenv("FAKE_SKILLS", "some-builtin")
    m = _meta(gen.generate_one("sparse_parity", "claude", "m1", "noexec"))
    assert m["status"] == "ok" and m["attempts"][0]["skills"] == ["some-builtin"]



# ---- v0.8: the fence is checked at the request level ---------------------------------

SESSION_2_1_318 = HERE / "fixtures" / "claude_session_2_1_318.jsonl"  # redacted real log (gridnav sample_03)


def test_real_2_1_318_requests_carried_the_advisor():
    """What the startup tool list hid: every request offered a deferred advisor server tool."""
    s = parse_session(SESSION_2_1_318)
    assert s["error"] is None and s["server_blocks"] == []   # offered, never invoked
    assert s["request_tools"] == ["DeferredToolPlaceholder", "Edit", "Read", "Write", "advisor"]
    v = request_violation("claude", "noexec", s["request_tools"], s["server_blocks"])
    assert "advisor" in v and "DeferredToolPlaceholder" in v


@pytest.mark.parametrize("request_tools,blocks,ok", [
    (["Edit", "Read", "Write"], [], True),
    (["Edit", "Read", "Write", "advisor"], [], False),
    (["Edit", "Read", "Write"], ["server_tool_use"], False),
    (None, [], False),                                       # no log -> fail closed
])
def test_request_violation_rule(request_tools, blocks, ok):
    assert (request_violation("claude", "noexec", request_tools, blocks) is None) == ok
    assert (fence_violation("claude", "noexec", ["Read", "Write", "Edit"], request_tools=request_tools,
                            server_blocks=blocks) is None) == ok
    assert request_violation("codex", "ro", request_tools, blocks) is None   # Codex keeps no such log


def test_session_log_is_copied_redacted(fake_env, monkeypatch):
    monkeypatch.setenv("FAKE_AGENT_MODE", "good")
    d = gen.generate_one("sparse_parity", "claude", "m1", "noexec")
    m = _meta(d)
    assert m["status"] == "ok", m["final_message"]
    a = m["attempts"][0]
    assert a["session_log"] == "attempt0.session.jsonl" and a["request_tools"] == ["Edit", "Read", "Write"]
    assert a["n_server_blocks"] == 0 and a["session_error"] is None
    text = (d / "attempt0.session.jsonl").read_text()
    assert "someone@example.edu" not in text and "<redacted-email>" in text
    assert "4c0ffee0-1111-4222-8333-444455556666" not in text and '"accountUuid": "<redacted-uuid>"' in text
    assert str(fake_env / "home") not in text and "`~/.claude-written-init/projects/" in text
    assert all(json.loads(line) for line in text.splitlines())


def test_redaction_of_account_ids_and_home():
    acct, org, msg = "aaaaaaaa-1111-4111-8111-111111111111", "bbbbbbbb-2222-4222-8222-222222222222", \
        "cccccccc-3333-4333-8333-333333333333"
    rows = [{"type": "session-owner", "accountUuid": acct, "organizationUuid": org, "sessionId": msg},
            {"type": "attachment", "uuid": msg, "text": f"org {org} said hi",
             "paths": ["/Users/me/.claude-written-init/x", "/Users/me", "/Users/meow/x", "/tmp/Users/me2"]}]
    text = "".join(json.dumps(r) + "\n" for r in rows) + f"raw {acct} /Users/me/y\n"
    lines = redact_log(text, home="/Users/me").splitlines()
    a, b = json.loads(lines[0]), json.loads(lines[1])
    assert a == {"type": "session-owner", "accountUuid": "<redacted-uuid>", "organizationUuid": "<redacted-uuid>",
                 "sessionId": msg}                                   # session/message ids are kept
    assert b["uuid"] == msg and b["text"] == "org <redacted-uuid> said hi"
    assert b["paths"] == ["~/.claude-written-init/x", "~", "/Users/meow/x", "/tmp/Users/me2"]
    assert lines[2] == "raw <redacted-uuid> ~/y"                     # a non-JSON line is redacted too


@pytest.mark.parametrize("env,needle", [
    ({"FAKE_REQUEST_TOOLS": "advisor,DeferredToolPlaceholder"}, "advisor"),
    ({"FAKE_SERVER_BLOCK": "session"}, "server-side tool blocks"),
    ({"FAKE_SERVER_BLOCK": "stream"}, "server-side tool blocks"),
    ({"FAKE_SESSION_LOG": "none"}, "session log was missing or unreadable"),
    ({"FAKE_SESSION_LOG": "garbage"}, "session log was missing or unreadable"),
])
def test_request_level_problems_stop_generation(fake_env, monkeypatch, env, needle):
    monkeypatch.setenv("FAKE_AGENT_MODE", "good")
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    d = gen.generate_one("sparse_parity", "claude", "m1", "noexec", max_retries=2)
    m = _meta(d)
    assert m["status"] == "fence_violation" and needle in m["final_message"]
    assert len(m["attempts"]) == 1 and not (d / "weights.npz").exists()
    assert any("fence violation" in f["message"] for f in m["transcript_flags"])


def test_redaction_keeps_json_valid_next_to_escapes():
    line = json.dumps({"a": "line one\nme@cs.stanford.edu wrote", "b": ["x@y.org"], "c": "react@18.3.1"})
    out = json.loads(redact_log(line + "\n", home="/Users/me"))
    assert out == {"a": "line one\n<redacted-email> wrote", "b": ["<redacted-email>"], "c": "react@18.3.1"}
    assert redact_log("not json a@b.io\n", home="/Users/me") == "not json <redacted-email>\n"


def test_isolation_check_fails_on_request_level_tools(fake_env):
    import subprocess
    env = {**os.environ, "FAKE_AGENT_MODE": "good", "FAKE_REQUEST_TOOLS": "advisor",
           "PYTHONPATH": str(ROOT / "src")}
    proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "check_isolation.py"), "--agent", "claude",
                           "--model", "m", "--condition", "noexec", "--results-dir", str(fake_env / "iso")],
                          capture_output=True, text=True, env=env, timeout=120)
    assert proc.returncode == 1, proc.stdout
    assert f"{'request_tools_exact':26s} LEAK" in proc.stdout and f"{'extra_tools':26s} blocked" in proc.stdout
    report = json.loads(next((fake_env / "iso").glob("*/report.json")).read_text())
    assert report["request_tools"] == ["Edit", "Read", "Write", "advisor"] and report["session_log"]
