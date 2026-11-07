"""scripts/scrub_publish.py: what is removed where, and that a broken JSON or a leak fails closed."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("scrub_publish", ROOT / "scripts" / "scrub_publish.py")
sp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sp)
IDS = {"1234-abcd": "<redacted-uuid>", "me@cs.example.edu": "<redacted-email>"}


def test_scrub_text():
    text = 'deny "/Users/me/**", other "/Users/meow", id 1234-abcd, x@y.org, me@cs.example.edu'
    out = sp.scrub_text(text, "inits/t/s/meta.json", IDS, "/Users/me")
    assert out == 'deny "~/**", other "/Users/meow", id <redacted-uuid>, <redacted-email>, <redacted-email>'
    kept = sp.scrub_text(text, "tests/test_agents.py", IDS, "/Users/me")   # fixture emails stay outside agent output
    assert "x@y.org" in kept and "1234-abcd" not in kept and "/Users/me/" not in kept


def test_broken_json_fails_closed():
    before = '{"a": "line\\nme@x.io"}'   # the email regex would eat the n of \n
    with pytest.raises(SystemExit, match="broke JSON"):
        sp.check_json("results/r/a.jsonl", before, sp.scrub_text(before, "results/r/a.jsonl", {}, "/Users/me"))


def test_leaks(tmp_path):
    (tmp_path / "results").mkdir()
    (tmp_path / "results" / "ok.md").write_text("~/projects and someone-else")
    (tmp_path / "results" / "bad.json").write_text('{"p": "/Users/me/x", "who": "me"}')
    (tmp_path / "tests.py").write_text("a@b.io 1234-abcd")
    (tmp_path / "results" / "fig.png").write_bytes(b"\x89PNG\xff TV@gk.Be")   # email-like bytes in a binary: not a leak
    assert sp.leaks(tmp_path, IDS, "/Users/me") == ["results/bad.json: home path", "results/bad.json: user name",
                                                     "tests.py: identifier"]
