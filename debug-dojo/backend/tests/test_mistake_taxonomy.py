import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import pytest
from app.runner import run_submission
from app.tagger import detect_mistakes
from app.main import find_challenge


def test_detect_off_by_one():
    challenge = find_challenge("first-n-squares")
    # Bug: range(n) starts from 0 and misses n
    code = """
def first_n_squares(n):
    return [i * i for i in range(n)]
"""
    result = run_submission(code, challenge)
    tags = detect_mistakes(code, result, challenge)
    assert "off_by_one" in tags


def test_detect_boundary_comparison():
    challenge = find_challenge("count-passes")
    # Bug: strict inequality > instead of >=
    code = """
def count_passes(marks, threshold=40):
    return sum(1 for m in marks if m > threshold)
"""
    result = run_submission(code, challenge)
    tags = detect_mistakes(code, result, challenge)
    assert "boundary_comparison" in tags


def test_detect_print_not_return():
    challenge = find_challenge("count-passes")
    # Bug: prints output instead of returning
    code = """
def count_passes(marks, threshold=40):
    res = sum(1 for m in marks if m >= threshold)
    print(res)
"""
    result = run_submission(code, challenge)
    tags = detect_mistakes(code, result, challenge)
    assert "print_not_return" in tags


def test_detect_mutates_input():
    challenge = find_challenge("middle-three")
    # Bug: mutates input by popping elements
    code = """
def middle_three(items):
    while len(items) > 3:
        items.pop(0)
        if len(items) > 3:
            items.pop()
    return items
"""
    result = run_submission(code, challenge)
    tags = detect_mistakes(code, result, challenge)
    assert "mutates_input" in tags


def test_detect_unhandled_short_input():
    challenge = find_challenge("safe-average")
    # Bug: crashes on empty list with ZeroDivisionError
    code = """
def safe_average(readings):
    return sum(readings) / len(readings)
"""
    result = run_submission(code, challenge)
    tags = detect_mistakes(code, result, challenge)
    assert "unhandled_short_input" in tags
