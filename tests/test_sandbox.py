import numpy as np
import pytest

from written_init.paths import INITS
from written_init.sandbox import check_source, extract_code, run_build

GOOD = "import numpy as np\n\ndef build_weights():\n    return {'W0': np.zeros((2, 2)), 'b0': np.zeros(2)}\n"


def test_accepts_clean_code():
    assert check_source(GOOD) == []


@pytest.mark.parametrize("snippet", [
    "import numpy as np\nX = np.random.rand(3)",
    "from numpy.random import default_rng",
    "import numpy.random as r",
    "import os",
    "import torch",
    "import numpy as np\nw = np.linalg.lstsq(a, b)",
    "import numpy as np\nw = np.linalg.pinv(a)",
    "f = getattr(np, 'rand' + 'om')",
    "x = ().__class__",
    "eval('1')",
    "open('data.csv')",
])
def test_rejects_rule_breaking_code(snippet):
    assert check_source(GOOD + snippet + "\n"), snippet


def test_requires_build_weights():
    assert check_source("import numpy as np\nx = 1\n")


def test_extract_code_picks_build_block():
    text = "Explanation.\n```python\nprint('hi')\n```\nMore.\n```python\n" + GOOD + "```\n"
    assert "def build_weights" in extract_code(text)
    assert extract_code("no code here") is None


def test_run_build_ok_and_errors(tmp_path):
    good = tmp_path / "good.py"; good.write_text(GOOD)
    ok, _ = run_build(good, tmp_path / "w.npz")
    assert ok and np.load(tmp_path / "w.npz")["W0"].shape == (2, 2)

    bad = tmp_path / "bad.py"; bad.write_text("def build_weights():\n    raise ValueError('boom')\n")
    ok, msg = run_build(bad, tmp_path / "w2.npz")
    assert not ok and "boom" in msg

    slow = tmp_path / "slow.py"; slow.write_text("def build_weights():\n    while True: pass\n")
    ok, msg = run_build(slow, tmp_path / "w3.npz", timeout_s=2)
    assert not ok and "time limit" in msg


@pytest.mark.parametrize("path", sorted(INITS.glob("*/reference/sample_*/build.py")), ids=lambda p: p.parts[-4])
def test_reference_inits_pass_rules(path):
    assert check_source(path.read_text()) == []
