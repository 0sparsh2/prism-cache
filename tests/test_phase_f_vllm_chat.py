"""Phase F vLLM chat probe (offline health path)."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_phase_f_vllm_chat_health_only():
    proc = subprocess.run(
        [sys.executable, str(ROOT / "examples" / "phase_f_vllm_chat.py")],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=True,
    )
    assert "Prefix fingerprint" in proc.stdout
    assert "vLLM not reachable" in proc.stdout or "vLLM: OK" in proc.stdout
