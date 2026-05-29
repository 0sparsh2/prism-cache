"""Smoke test for org scenario script."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_org_scenario_small_run():
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "examples" / "org_scenario_tier3.py"),
            "--users",
            "5",
            "--vector-latency-ms",
            "0",
        ],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=True,
    )
    assert "Tier 3 hit rate" in proc.stdout
    assert "Vector DB calls" in proc.stdout
