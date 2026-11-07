"""Generate written inits with headless coding agents (Claude Code, Codex CLI).

No API keys: each agent uses its own CLI login. Every run happens in a fresh
temporary workspace outside the repository, with tools restricted per
condition, and its full event transcript is saved for audit.
"""

# (agent, condition) pairs that exist. See prompts/conditions/ and runners.py.
CONDITIONS = {
    "claude": ("noexec", "tools"),
    "codex": ("ro", "tools"),
}

# Conditions where the agent writes build.py itself; otherwise it replies with code.
WRITABLE = {("claude", "noexec"), ("claude", "tools"), ("codex", "tools")}
