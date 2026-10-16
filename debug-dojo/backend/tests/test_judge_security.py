import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import pytest
from app.runner import run_submission
from app.main import find_challenge


def test_sandbox_blocks_sockets():
    challenge = find_challenge("last-k-total")
    malicious_code = """
import socket
def last_k_total(marks, k):
    s = socket.socket()
    return sum(marks)
"""
    result = run_submission(malicious_code, challenge)
    assert any(t["outcome"] == "runtime_error" for t in result["visible"])


def test_sandbox_blocks_process_spawning():
    challenge = find_challenge("last-k-total")
    malicious_code = """
import subprocess
def last_k_total(marks, k):
    subprocess.run(["echo", "hacked"])
    return sum(marks)
"""
    result = run_submission(malicious_code, challenge)
    assert any(t["outcome"] == "runtime_error" for t in result["visible"])


def test_sandbox_blocks_os_system():
    challenge = find_challenge("last-k-total")
    malicious_code = """
import os
def last_k_total(marks, k):
    os.system("echo hacked")
    return sum(marks)
"""
    result = run_submission(malicious_code, challenge)
    assert any(t["outcome"] == "runtime_error" for t in result["visible"])


def test_sandbox_timeout():
    challenge = find_challenge("last-k-total")
    infinite_loop_code = """
def last_k_total(marks, k):
    while True:
        pass
    return sum(marks)
"""
    result = run_submission(infinite_loop_code, challenge)
    assert any(t["outcome"] == "timeout" for t in result["visible"])


def test_sandbox_output_limit():
    challenge = find_challenge("last-k-total")
    flood_code = """
def last_k_total(marks, k):
    print("A" * 10000)
    return sum(marks)
"""
    result = run_submission(flood_code, challenge)
    assert any(t["outcome"] == "runtime_error" for t in result["visible"])


def test_hidden_tests_never_leak_values():
    challenge = find_challenge("last-k-total")
    code = """
def last_k_total(marks, k):
    return 0
"""
    result = run_submission(code, challenge)
    hidden = result["hidden"]
    assert len(hidden) > 0
    for h in hidden:
        # Rule 2: Strictly no inputs, expected, or actual outputs in hidden results
        assert "call" not in h
        assert "input" not in h
        assert "expected" not in h
        assert "got" not in h
        assert "error" not in h
        assert "args" not in h
        assert h["outcome"] in ("passed", "wrong_output", "runtime_error", "timeout")
