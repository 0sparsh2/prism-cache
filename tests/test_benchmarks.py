"""CI gate: reproducible eval benchmarks must pass."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from eval.benchmarks import run_all_benchmarks  # noqa: E402


def test_eval_benchmarks_pass():
    report = run_all_benchmarks()
    failures = [r for r in report.rows if not r.passed]
    assert not failures, failures
