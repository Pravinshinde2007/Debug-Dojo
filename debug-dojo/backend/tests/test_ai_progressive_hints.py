import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db import init_db
from app.llm import (
    synthesize_grounded_hint,
    generate_ai_progressive_hint,
    get_optimal_gemini_model,
    explain_runtime_error,
    leak_guard,
    DEFAULT_FLASH_MODEL,
    DEFAULT_PRO_MODEL
)

client = TestClient(app)


def test_hints_are_100_percent_unique_across_all_levels():
    """Verify that Hints 1 through 5 are completely distinct and never repeat."""
    challenge = {
        "id": "last-k-total",
        "title": "Last K Total",
        "difficulty": "Easy",
        "hints": [
            "Review the core invariant: the function sums up to the last k marks, but should return 0 whenever k is 0 or marks is empty.",
            "Inspect how you slice: in Python, marks[-0:] selects the entire list instead of an empty slice!",
            "Algorithmic Approach: 1. If k <= 0 or not marks, return 0. 2. Clamp k with min(k, len(marks)). 3. Sum the last k elements.",
            "Edge Case Analysis: When k exceeds len(marks), you should sum all elements. When k is 0, make sure your slice does not wrap to the full list.",
            "Structural Guidance: Clamp k = min(k, len(marks)) and return sum(marks[-k:]) guarded by an 'if k > 0' check."
        ]
    }
    code = "def last_k_total(marks, k):\n    return sum(marks[-k:])\n"
    
    collected_hints = []
    for lvl in range(1, 6):
        res = synthesize_grounded_hint(
            challenge=challenge,
            code=code,
            hint_level=lvl,
            error_line=2,
            failed_call="last_k_total([], 3)",
            expected="0",
            got="0"
        )
        assert res["hint_level"] == lvl
        assert res["hint"] not in collected_hints, f"Hint level {lvl} was duplicate of earlier hint!"
        collected_hints.append(res["hint"])

    assert len(collected_hints) == 5
    assert len(set(collected_hints)) == 5


def test_hint_level_2_contains_line_number():
    """Verify that Hint level 2 specifically inspects the exact line in student code."""
    challenge = {"id": "sample-challenge", "title": "Sample"}
    code = "def solve(items):\n    # line 2\n    total = items[0] / 0\n    return total\n"
    
    res = synthesize_grounded_hint(
        challenge=challenge,
        code=code,
        hint_level=2,
        error_line=3,
        error_type="ZeroDivisionError",
        error_msg="division by zero"
    )
    assert "Line 3" in res["hint"] or "line 3" in res["hint"].lower()
    assert "zerodivision" in res["hint"].lower() or "divide by zero" in res["hint"].lower()


def test_runtime_error_extraction_with_line_number():
    """Verify explain_runtime_error extracts line number and beginner explanation."""
    stderr = """
Traceback (most recent call last):
  File "solution.py", line 7, in calculate_average
    return total / len(numbers)
ZeroDivisionError: division by zero
"""
    err = explain_runtime_error(stderr)
    assert err["line_number"] == 7
    assert err["error_type"] == "ZeroDivisionError"
    assert "Line 7" in err["message"]
    assert "zero" in err["message"].lower()


def test_index_error_extraction_with_line_number():
    """Verify IndexError extracts out-of-range bounds explanation."""
    stderr = """
Traceback (most recent call last):
  File "solution.py", line 4, in get_item
    return items[10]
IndexError: list index out of range
"""
    err = explain_runtime_error(stderr)
    assert err["line_number"] == 4
    assert err["error_type"] == "IndexError"
    assert "Line 4" in err["message"]
    assert "out of range" in err["message"].lower() or "index" in err["message"].lower()


def test_timeout_tle_identification_and_explanation():
    """Verify Time Limit Exceeded (TLE) is detected and gives infinite loop hints."""
    res = synthesize_grounded_hint(
        challenge={"id": "find-loop", "title": "Loop Test"},
        code="while True:\n    pass\n",
        hint_level=1,
        error_type="Timeout",
        error_msg="Execution timed out after 2.0s"
    )
    assert "Time Limit Exceeded" in res["hint"] or "TLE" in res["hint"] or "timed out" in res["hint"].lower()
    assert "loop" in res["hint"].lower()


def test_model_tiering_flash_vs_pro():
    """Verify standard problems use Gemini Flash and complex problems tier to Gemini Pro."""
    # Standard beginner task -> Flash
    standard_desc = "Given a list of student marks, return how many students passed with mark >= 40."
    assert get_optimal_gemini_model(standard_desc) == DEFAULT_FLASH_MODEL

    # Advanced algorithm (Dynamic Programming / Graph / 10^5 constraints) -> Pro
    dp_desc = "Find the shortest path in a weighted directed acyclic graph using dynamic programming with N = 10^5 vertices."
    assert get_optimal_gemini_model(dp_desc) == DEFAULT_PRO_MODEL


def test_leak_guard_strips_full_solution_code():
    """Verify Rule 4 Leak Guard strips fenced code and function definitions."""
    raw_leak = "Here is the answer:\n```python\ndef last_k_total(marks, k):\n    return sum(marks[-k:])\n```"
    guarded = leak_guard(raw_leak)
    assert "```" not in guarded
    assert "def last_k_total" not in guarded


def test_api_hint_endpoint_chronological_progression():
    """Test /api/hint endpoint returns progressive distinct hints with payload context."""
    for lvl in range(1, 6):
        resp = client.post(
            "/api/hint",
            json={
                "submission_id": f"test_sub_{lvl}",
                "challenge_id": "last-k-total",
                "code": "def last_k_total(marks, k):\n    return sum(marks[-k:])\n",
                "hint_level": lvl,
                "error_type": "Wrong Output",
                "failed_call": "last_k_total([], 3)",
                "expected": "0",
                "got": "None"
            }
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["hint_index"] == lvl
        assert len(data["hint"]) > 10
        assert data["model_used"] is not None
        assert "def last_k_total" not in data["hint"]
