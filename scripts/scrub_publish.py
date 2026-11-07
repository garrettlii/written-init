"""Copy the repo to publish/ with personal identifiers removed, for a public push (PLAN.md week 5).

Copies every file `git add -A` would commit (tracked plus untracked, minus .gitignore), except
EXCLUDE, and never edits the originals. Removes the home path (-> ~, as redact_log does for session logs), any email in
inits/ and results/ (agent and CLI output; tests/ keep their fake fixture emails), and, everywhere,
the exact email, account/org UUIDs and user ID of the local Claude profiles and the git email. Then
verifies publish/ has 0 matches and that every JSON file and line that parsed still parses.
Identifiers are never printed.

  uv run python scripts/scrub_publish.py [--out publish]

Push publish/ as a fresh repository: this repo's history still holds the unscrubbed files.
"""

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path

from written_init.agents.runners import _EMAIL
from written_init.paths import ROOT

AGENT_OUTPUT = ("inits/", "results/")
# Not published: this repo's own coding-assistant setup and patch notes, not part of the study record.
EXCLUDE = ("CLAUDE.md", "UPDATE.md", ".claude/")
PROFILES = (Path.home() / ".claude.json", Path.home() / ".claude-written-init" / ".claude.json")


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def local_identifiers() -> dict[str, str]:
    """Exact private strings -> placeholder."""
    out = {}
    for p in PROFILES:
        if p.exists():
            d = json.loads(p.read_text())
            acct = d.get("oauthAccount") or {}
            for key, ph in (("emailAddress", "<redacted-email>"), ("accountUuid", "<redacted-uuid>"),
                            ("organizationUuid", "<redacted-uuid>")):
                if acct.get(key):
                    out[acct[key]] = ph
            if d.get("userID"):
                out[d["userID"]] = "<redacted-id>"
    email = subprocess.run(["git", "config", "user.email"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    if email:
        out[email] = "<redacted-email>"
    return out


def _home_re(home: str) -> re.Pattern:
    return re.compile(re.escape(home) + r"(?![A-Za-z0-9._-])")


def scrub_text(text: str, rel: str, identifiers: dict[str, str], home: str) -> str:
    for value in sorted(identifiers, key=len, reverse=True):
        text = text.replace(value, identifiers[value])
    if rel.startswith(AGENT_OUTPUT):
        text = _EMAIL.sub("<redacted-email>", text)
    return _home_re(home).sub("~", text)


def _parses(s: str) -> bool:
    try:
        json.loads(s)
        return True
    except json.JSONDecodeError:
        return False


def check_json(rel: str, before: str, after: str) -> None:
    """Fail closed if scrubbing broke JSON that parsed before (e.g. an email right after an escape)."""
    pairs = [(before, after)] if rel.endswith(".json") else \
        list(zip(before.splitlines(), after.splitlines())) if rel.endswith(".jsonl") else []
    if any(_parses(b) and not _parses(a) for b, a in pairs):
        raise SystemExit(f"scrubbing broke JSON in {rel}; nothing should be pushed until this is fixed")


def _is_utf8(data: bytes) -> bool:
    try:
        data.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def leaks(out: Path, identifiers: dict[str, str], home: str) -> list[str]:
    """Files in `out` that still contain an identifier, the home path, the bare user name or (in text
    files under inits/ and results/) an email. Binary files are searched for all but the email
    pattern, which compressed bytes can match by chance."""
    user = re.escape(Path(home).name)
    checks = [("identifier", re.compile("|".join(map(re.escape, identifiers))) if identifiers else None),
              ("home path", _home_re(home)), ("user name", re.compile(rf"(?<![A-Za-z0-9]){user}(?![A-Za-z0-9])"))]
    found = []
    for f in sorted(p for p in out.rglob("*") if p.is_file()):
        rel = f.relative_to(out).as_posix()
        data = f.read_bytes()
        text = data.decode("utf-8", errors="ignore")
        is_text = _is_utf8(data)
        for what, pat in checks + ([("email", _EMAIL)] if is_text and rel.startswith(AGENT_OUTPUT) else []):
            if pat is not None and pat.search(text):
                found.append(f"{rel}: {what}")
    return found


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--out", default=str(ROOT / "publish"))
    a = p.parse_args()
    out = Path(a.out)
    if out.exists():
        raise SystemExit(f"{out} exists; delete it after checking what is in it, then rerun")
    identifiers, home = local_identifiers(), str(Path.home())
    files = [f for f in git("ls-files", "--cached", "--others", "--exclude-standard").splitlines()
             if not f.startswith(EXCLUDE)]
    changed = 0
    for rel in files:
        src, dst = ROOT / rel, out / rel
        if not src.is_file():
            continue  # deleted in the working tree
        dst.parent.mkdir(parents=True, exist_ok=True)
        data = src.read_bytes()
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            dst.write_bytes(data)  # binary (weights, figures): copied as is, still searched below
        else:
            new = scrub_text(text, rel, identifiers, home)
            check_json(rel, text, new)
            dst.write_bytes(new.encode("utf-8"))
            changed += new != text
        shutil.copymode(src, dst)
    found = leaks(out, identifiers, home)
    dirty = bool(git("status", "--porcelain"))
    print(f"copied {len(files)} files to {out}, scrubbed {changed}; source commit {git('rev-parse', '--short', 'HEAD')}"
          f"{' plus uncommitted changes' if dirty else ''}. Identifiers checked: {len(identifiers)} exact, plus the home "
          "path, the user name and emails.")
    if found:
        raise SystemExit("LEAKS (do not push):\n" + "\n".join(found))
    print("verify: 0 matches in publish/")


if __name__ == "__main__":
    main()
