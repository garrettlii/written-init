"""Mark a written sample as audited after reviewing its build.py.

  uv run python scripts/mark_audited.py inits/gridnav/claude-opus-5-5/sample_00 --notes "closed-form; no fitting"
  uv run python scripts/mark_audited.py inits/gridnav/claude-opus-5-5/sample_01 --reject --notes "enumerates inputs and solves"

Rejected samples keep their files but are renamed to rejected_XX so no sweep can use them.
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("sample_dir")
p.add_argument("--notes", required=True)
p.add_argument("--by", default="garrett")
p.add_argument("--reject", action="store_true")
a = p.parse_args()

d = Path(a.sample_dir)
meta_path = d / "meta.json"
meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
meta.update(audited=not a.reject, audit_notes=a.notes, audited_by=a.by,
            audited_at=datetime.now(timezone.utc).isoformat(), rejected=a.reject)
meta_path.write_text(json.dumps(meta, indent=2))
if a.reject:
    new = d.with_name(d.name.replace("sample_", "rejected_"))
    d.rename(new)
    print(f"rejected -> {new}")
else:
    print(f"audited: {d}")
