"""One-time setup of the dedicated agent profiles used for every generation.

Each profile is an empty config directory with its own subscription login, so
your plugins, hooks, global instructions and skills never reach the agent.

  uv run python scripts/setup_profiles.py --agent claude
  uv run python scripts/setup_profiles.py --agent codex

Log in with the same account you normally use. Nothing is copied from your
regular ~/.claude or ~/.codex. Never install plugins or add instructions to
these profiles; generation refuses to run if you do.

Safe to rerun on an existing profile (v0.7): it merges the required settings,
including the claude.ai skill/plugin sync opt-outs, into settings.json and
moves anything already synced into .trash/ (recoverable), which is what
Claude Code itself does on its next start once sync is off.
"""

import argparse
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone

from written_init.agents.runners import (PROFILE_ENV, REQUIRED_CLAUDE_PROFILE_SETTINGS, STRIPPED_ENV,
                                        check_profile, profile_dir)


def migrate_claude_profile(d) -> list[str]:
    """Merge required settings; move synced skills/plugins into .trash/. Returns what changed."""
    changed = []
    f = d / "settings.json"
    cfg = json.loads(f.read_text() or "{}") if f.exists() else {}
    for k, v in REQUIRED_CLAUDE_PROFILE_SETTINGS.items():
        if cfg.get(k) != v:
            cfg[k] = v
            changed.append(f"settings.json: {k} = {json.dumps(v)}")
    f.write_text(json.dumps(cfg, indent=2) + "\n")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    for kind in ("skills", "plugins"):
        synced = d / kind / "synced"
        if not synced.is_dir():
            continue
        items = [x for x in synced.iterdir()]
        if not any(y.is_file() and not y.name.startswith(".") for x in items
                   for y in ([x] if x.is_file() else x.rglob("*"))):
            continue
        dest = d / kind / ".trash" / f"synced_{stamp}"
        dest.mkdir(parents=True, exist_ok=True)
        for x in items:
            shutil.move(str(x), str(dest / x.name))
        changed.append(f"moved {kind}/synced/ -> {dest.relative_to(d)}")
    return changed

LOGIN = {"claude": ["claude", "auth", "login"], "codex": ["codex", "login"]}
STATUS = {"claude": ["claude", "auth", "status"], "codex": ["codex", "login", "status"]}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--agent", required=True, choices=["claude", "codex"])
    p.add_argument("--no-login", action="store_true", help="only create the folder")
    a = p.parse_args()

    d = profile_dir(a.agent)
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d, 0o700)
    if a.agent == "claude":
        for c in migrate_claude_profile(d):
            print(f"  {c}")
    check_profile(a.agent)
    print(f"profile ready: {d}")

    env = {k: v for k, v in os.environ.items() if k not in STRIPPED_ENV}
    env[PROFILE_ENV[a.agent]] = str(d)
    if shutil.which(a.agent) is None:
        print(f"{a.agent} is not on PATH; install it, then rerun this script to log in")
        return
    if not a.no_login:
        print(f"logging in ({' '.join(LOGIN[a.agent])}) with {PROFILE_ENV[a.agent]}={d}")
        subprocess.run(LOGIN[a.agent], env=env)
    st = subprocess.run(STATUS[a.agent], env=env, capture_output=True, text=True)
    print((st.stdout + st.stderr).strip() or f"(no output from {' '.join(STATUS[a.agent])})")
    print("logged in" if st.returncode == 0 else
          f"status check exited {st.returncode}: run `{PROFILE_ENV[a.agent]}={d} {' '.join(LOGIN[a.agent])}` yourself")


if __name__ == "__main__":
    main()
