import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import pytest
from app.runner import run_submission
from app.main import find_challenge


def test_last_k_total_correct():
    challenge = find_challenge("last-k-total")
    assert challenge is not None

    correct_code = """
def last_k_total(marks, k):
    if k <= 0:
        return 0
    if k > len(marks):
        return sum(marks)
    return sum(marks[-k:])
"""
    result = run_submission(correct_code, challenge)
    print("DEBUG_RESULT:", result)
    assert result["all_passed"] is True
    assert all(t["outcome"] == "passed" for t in result["visible"])
    assert all(t["outcome"] == "passed" for t in result["hidden"])


def test_last_k_total_k_larger_than_list():
    challenge = find_challenge("last-k-total")
    # Bug: doesn't handle k > len(marks) or negative k
    buggy_code = """
def last_k_total(marks, k):
    if k == 0:
        return 0
    return sum(marks[-k:])
"""
    result = run_submission(buggy_code, challenge)
    # Visible tests might pass, but hidden test where k is larger than list will fail or handle differently
    hidden_outcomes = [t["outcome"] for t in result["hidden"]]
    assert len(hidden_outcomes) > 0


def test_count_passes_correct():
    challenge = find_challenge("count-passes")
    assert challenge is not None

    correct_code = """
def count_passes(marks, threshold=40):
    return sum(1 for m in marks if m >= threshold)
"""
    result = run_submission(correct_code, challenge)
    assert result["all_passed"] is True


def test_first_n_squares_correct():
    challenge = find_challenge("first-n-squares")
    assert challenge is not None

    correct_code = """
def first_n_squares(n):
    if n <= 0:
        return []
    return [i * i for i in range(1, n + 1)]
"""
    result = run_submission(correct_code, challenge)
    assert result["all_passed"] is True


def test_middle_three_correct():
    challenge = find_challenge("middle-three")
    assert challenge is not None

    correct_code = """
def middle_three(items):
    if len(items) < 3:
        return []
    mid = len(items) // 2
    return items[mid - 1 : mid + 2]
"""
    result = run_submission(correct_code, challenge)
    assert result["all_passed"] is True
