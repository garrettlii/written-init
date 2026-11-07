"""Parse agent transcripts into one normalized shape, and flag suspicious activity.

The parsers are deliberately forgiving (event formats change between CLI
versions): unknown events are skipped, never fatal. Flags are heuristics that
point a human auditor at lines worth reading. They do not replace the audit.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


def _lines(path: Path):
    if not path.exists():
        return
    for line in path.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(ev, dict):
            yield ev


def _text_of(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(_text_of(c.get("text", c.get("content", ""))) if isinstance(c, dict) else str(c)
                         for c in content)
    return "" if content is None else str(content)


def parse(agent: str, path: Path, workspace: Path | None = None, session_log: Path | None = None) -> dict:
    out = {"tool_calls": [], "commands": [], "web": [], "denials": [], "tool_outputs": [],
           "final_text": None, "available_tools": None, "model": None, "cost_usd": None,
           "num_turns": None, "usage": None, "errors": [], "hook_events": [], "plugins": None, "skills": None,
           "session_id": None, "request_tools": None, "server_blocks": [], "session_error": None,
           "agents": None}
    if agent == "claude":
        _parse_claude(path, out)
        s = parse_session(session_log)
        out["request_tools"], out["session_error"] = s["request_tools"], s["error"]
        out["server_blocks"] += s["server_blocks"]
    elif agent == "codex":
        _parse_codex(path, out)
    else:
        raise ValueError(agent)
    return out


def _server_blocks(obj) -> list[str]:
    """Types of server-side tool blocks anywhere inside obj (server_tool_use, advisor_tool_result,
    web_search_tool_result, ...). Client tool results are plain `tool_result` and don't count."""
    if isinstance(obj, list):
        return [b for x in obj for b in _server_blocks(x)]
    if not isinstance(obj, dict):
        return []
    t = obj.get("type")
    own = [t] if isinstance(t, str) and (t == "server_tool_use"
                                         or (t.endswith("_tool_result") and t != "tool_result")) else []
    return own + [b for v in obj.values() for b in _server_blocks(v)]


def parse_session(path: Path | None) -> dict:
    """Claude Code's own session log (v0.8): the tools every API request carried, which the
    startup event leaves out for server-side and deferred tools. Strict, unlike the transcript
    parsers: any unreadable line or request without a logged tool list makes it unverifiable."""
    res = {"request_tools": None, "server_blocks": [], "error": None}
    if path is None or not path.exists():
        res["error"] = "session log not found"
        return res
    try:
        rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        res["error"] = f"session log is not valid JSONL ({e})"
        return res
    rows = [r for r in rows if isinstance(r, dict)]
    shapes = {r.get("shapeHash"): r.get("shape") for r in rows if r.get("type") == "api-request-shape"}
    requests = [r for r in rows if r.get("type") == "api-request"]
    used = [shapes.get(r.get("shapeHash")) for r in requests]
    if not requests or not all(isinstance(s, dict) and isinstance(s.get("tools"), list) for s in used):
        res["error"] = "session log has no API request with a logged tool list"
        return res
    res["request_tools"] = sorted({str(t.get("name") or t.get("type")) if isinstance(t, dict) else str(t)
                                   for s in used for t in s["tools"]})
    res["server_blocks"] = _server_blocks(rows)
    return res


def _parse_claude(path: Path, out: dict) -> None:
    for ev in _lines(path):
        t = ev.get("type")
        if out["session_id"] is None and ev.get("session_id"):
            out["session_id"] = str(ev["session_id"])
        out["server_blocks"] += _server_blocks(ev)
        # Any hook activity (e.g. a plugin's SessionStart hook_response) means text we didn't
        # write may have reached the model. Match loosely: event names vary across versions.
        if "hook" in str(t).lower() or "hook" in str(ev.get("subtype", "")).lower():
            out["hook_events"].append(ev)
        if t == "system" and ev.get("subtype") == "init":
            out["available_tools"] = ev.get("tools")
            out["model"] = ev.get("model")
            plugins = ev.get("plugins")
            out["plugins"] = [p.get("name", p) if isinstance(p, dict) else p for p in plugins] \
                if isinstance(plugins, list) else None
            agents = ev.get("agents")
            out["agents"] = [str(x.get("name", x)) if isinstance(x, dict) else str(x) for x in agents] \
                if isinstance(agents, list) else None
            names = []
            for key in ("skills", "slash_commands"):
                v = ev.get(key)
                if isinstance(v, list):
                    names += [x.get("name", x) if isinstance(x, dict) else x for x in v]
            out["skills"] = [str(n) for n in names] if names else None
        elif t == "assistant":
            for block in (ev.get("message") or {}).get("content") or []:
                if block.get("type") == "tool_use":
                    name, inp = block.get("name"), block.get("input") or {}
                    out["tool_calls"].append({"name": name, "input": inp})
                    if name == "Bash":
                        out["commands"].append(str(inp.get("command", "")))
                    if name in ("WebSearch", "WebFetch"):
                        out["web"].append(json.dumps(inp))
        elif t == "user":
            for block in (ev.get("message") or {}).get("content") or []:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    out["tool_outputs"].append(_text_of(block.get("content")))
        elif t == "result":
            out["final_text"] = ev.get("result")
            out["cost_usd"] = ev.get("total_cost_usd")
            out["num_turns"] = ev.get("num_turns")
            out["usage"] = ev.get("usage")
            out["denials"].extend(ev.get("permission_denials") or [])
            if ev.get("is_error") or (ev.get("subtype") not in (None, "success")):
                out["errors"].append(ev.get("subtype") or "error")
        elif t == "system" and "denied" in str(ev.get("subtype", "")):
            out["denials"].append(ev)


def _parse_codex(path: Path, out: dict) -> None:
    for ev in _lines(path):
        t = ev.get("type", "")
        if t.startswith("item."):
            item = ev.get("item") or {}
            kind = item.get("type") or item.get("item_type")
            if t != "item.completed":
                continue
            if kind == "command_execution":
                out["commands"].append(str(item.get("command", "")))
                out["tool_outputs"].append(str(item.get("aggregated_output", "")))
                out["tool_calls"].append({"name": "command_execution", "input": {"command": item.get("command")},
                                          "exit_code": item.get("exit_code")})
            elif kind == "web_search":
                out["web"].append(json.dumps(item))
            elif kind == "file_change":
                out["tool_calls"].append({"name": "file_change", "input": item})
            elif kind == "mcp_tool_call":
                out["tool_calls"].append({"name": "mcp_tool_call", "input": item})
            elif kind in ("agent_message", "assistant_message"):
                out["final_text"] = item.get("text")
        elif t == "turn.completed":
            out["usage"] = ev.get("usage")
        elif t in ("turn.failed", "error"):
            out["errors"].append(json.dumps(ev)[:500])


_FITTING = re.compile(r"\b(lstsq|pinv|solve|minimi[sz]e|optimi[sz]e|gradient|backprop|np\.random|random\.)\b")
_DATA = re.compile(r"sklearn|load_digits|digits\.csv|scikit")
_REPO_HINT = re.compile(r"written[_-]init")
_EXPLORE = re.compile(r"(^|[\s;&|])(find|ls|tree|du)\s+(/|~|\.\.)|\$HOME|os\.listdir\(['\"](/|~)")


def latest_isolation_roster(agent: str, condition: str, iso_dir: Path) -> dict | None:
    """Agent roster in the most recent PASSING isolation report for (agent, condition):
    {"report": dir, "agents": list | None}, or None if no passing report exists (v1.1)."""
    passing = []
    for p in iso_dir.glob("*/report.json"):
        try:
            r = json.loads(p.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if r.get("agent") == agent and r.get("condition") == condition and r.get("unexpected_leaks") == []:
            passing.append((p.parent.name, r))  # names end in a sortable UTC stamp
    if not passing:
        return None
    name, r = max(passing, key=lambda x: x[0])
    return {"report": str(iso_dir / name), "agents": r.get("agents")}


def roster_flag(agents: list[str] | None, ref: dict | None) -> dict | None:
    """Harness-drift signal, not a fence check (v1.1): subagents are unreachable without the
    Agent/Task tool, whose absence the request-level check already guarantees."""
    if ref is None or ref.get("agents") is None:
        return {"severity": "red", "message": "agent roster not compared: no passing isolation report records one",
                "evidence": json.dumps({"agents": agents, "report": ref and ref["report"]})}
    now, then = set(agents or []), set(ref["agents"])
    if now == then:
        return None
    return {"severity": "red", "message": f"agent roster differs from isolation report {Path(ref['report']).name}: "
                                          f"added {sorted(now - then)}, removed {sorted(then - now)}",
            "evidence": json.dumps({"agents": agents, "report_agents": ref["agents"]})}


def _paths_in(inp: dict) -> list[str]:
    return [str(v) for k, v in inp.items() if k in ("file_path", "path", "notebook_path") and v]


def flags(parsed: dict, agent: str, condition: str, workspace: Path, repo_root: Path) -> list[dict]:
    """Return [{severity: red|info, message, evidence}] for the auditor."""
    f: list[dict] = []
    ws = str(workspace.resolve())
    repo = str(repo_root.resolve())

    def add(sev, msg, ev=""):
        f.append({"severity": sev, "message": msg, "evidence": str(ev)[:400]})

    if parsed["web"]:
        add("red", f"{len(parsed['web'])} web search/fetch call(s)", parsed["web"][0])
    if parsed["denials"]:
        add("red", f"{len(parsed['denials'])} permission denial(s): the agent tried something outside its fence",
            parsed["denials"][0])
    if agent == "claude" and condition == "noexec" and parsed["commands"]:
        add("red", "commands executed in the noexec condition", parsed["commands"][0])
    if agent == "codex" and condition == "ro" and parsed["commands"]:
        add("info", f"{len(parsed['commands'])} read-only command(s) ran (Codex cannot disable its shell)",
            parsed["commands"][0])
    from .runners import fence_violation
    v = fence_violation(agent, condition, parsed["available_tools"], parsed["hook_events"], parsed["plugins"],
                        parsed["skills"], parsed["request_tools"], parsed["server_blocks"])
    if v:
        add("red", f"fence violation: {v}", {"startup": parsed["available_tools"],
                                             "requests": parsed["request_tools"]})

    texts = parsed["commands"] + [json.dumps(c["input"]) for c in parsed["tool_calls"]]
    for s in texts:
        if repo in s or _REPO_HINT.search(s):
            add("red", "referenced the project repository", s); break
    for s in texts:
        if _DATA.search(s):
            add("red", "touched sklearn or the digits data", s); break
    for s in parsed["commands"]:
        if _EXPLORE.search(s):
            add("red", "explored the filesystem outside the workspace", s); break
    for s in parsed["commands"]:
        if _FITTING.search(s):
            add("red", "executed code with fitting/solving/randomness keywords", s); break
    for c in parsed["tool_calls"]:
        for p in _paths_in(c["input"]):
            q = Path(p).expanduser()
            q = q if q.is_absolute() else Path(ws) / q
            try:
                rp = str(q.resolve())
            except OSError:
                rp = str(q)
            if not (rp == ws or rp.startswith(ws + "/")):
                add("red", f"{c['name']} on a path outside the workspace", p); break
    if parsed["errors"]:
        add("info", "agent reported errors", parsed["errors"][0])
    return f
