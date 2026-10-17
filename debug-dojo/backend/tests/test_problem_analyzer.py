import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db import init_db

client = TestClient(app)


def setup_module():
    init_db()


def test_analyze_problem_validation():
    # Empty problem statement should be rejected
    res = client.post("/api/analyze-problem", json={"problem_statement": ""})
    assert res.status_code == 400
    assert "empty" in res.json()["detail"].lower()

    # Oversized problem statement (>32KB) should be rejected
    res_large = client.post("/api/analyze-problem", json={"problem_statement": "A" * 35000})
    assert res_large.status_code == 400
    assert "exceeds" in res_large.json()["detail"].lower()


def test_analyze_problem_success():
    problem = """
    Given an array of integers nums and an integer target, return indices of the two numbers such that they add up to target.
    Assume exactly one solution exists, and you may not use the same element twice.
    """
    res = client.post("/api/analyze-problem", json={"problem_statement": problem, "user_id": "test_user_1"})
    assert res.status_code == 200
    data = res.json()
    assert "title" in data
    assert "summary" in data
    assert "constraints" in data
    assert len(data.get("sample_test_cases", [])) == 2
    assert len(data.get("hidden_test_cases", [])) >= 5
    assert data.get("reference_verified") is True


def test_run_code_sample_pass():
    spec = {
        "title": "Sum Two Numbers",
        "summary": "Read two integers and print their sum.",
        "sample_test_cases": [
            {"input": "3 5", "expected_output": "8"},
            {"input": "10 20", "expected_output": "30"}
        ],
        "hidden_test_cases": [
            {"input": "0 0", "expected_output": "0", "is_edge_case": True},
            {"input": "-5 5", "expected_output": "0", "is_edge_case": True},
            {"input": "100 200", "expected_output": "300", "is_edge_case": False},
            {"input": "-10 -20", "expected_output": "-30", "is_edge_case": True},
            {"input": "1000 2000", "expected_output": "3000", "is_edge_case": False}
        ]
    }

    correct_py = """import sys
tokens = sys.stdin.read().split()
if tokens:
    print(int(tokens[0]) + int(tokens[1]))
"""

    res = client.post("/api/run-code", json={
        "code": correct_py,
        "language": "python",
        "problem_spec": spec,
        "mode": "run",
        "user_id": "test_user_1"
    })
    assert res.status_code == 200
    data = res.json()
    results = data["test_results"]
    assert results["all_passed"] is True
    assert results["passed_count"] == 2
    feedback = data["feedback"]
    assert "Solved" in feedback["summary"] or "Optimal" in feedback.get("complexity_tip", "")


def test_run_code_logical_error_and_submit():
    spec = {
        "title": "Sum Two Numbers",
        "summary": "Read two integers and print their sum.",
        "sample_test_cases": [
            {"input": "3 5", "expected_output": "8"}
        ],
        "hidden_test_cases": [
            {"input": "0 0", "expected_output": "0", "is_edge_case": True},
            {"input": "10 20", "expected_output": "30", "is_edge_case": False}
        ]
    }

    # Wrong code: multiplies instead of adding
    buggy_py = """import sys
tokens = sys.stdin.read().split()
if tokens:
    print(int(tokens[0]) * int(tokens[1]))
"""

    res = client.post("/api/run-code", json={
        "code": buggy_py,
        "language": "python",
        "problem_spec": spec,
        "mode": "submit",
        "user_id": "test_user_1"
    })
    assert res.status_code == 200
    data = res.json()
    results = data["test_results"]
    assert results["all_passed"] is False
    assert results["failed_count"] >= 1
    feedback = data["feedback"]
    assert feedback["logic_explanation"] is not None
    assert "hints" in feedback
    assert "level_1" in feedback["hints"]


def test_get_feedback_progressive_hints():
    spec = {"title": "Sample", "summary": "Sample test"}
    test_results = {
        "all_passed": False,
        "tests": [
            {"status": "failed", "input": "5", "expected": "10", "got": "5"}
        ]
    }

    # Level 1 hint
    res1 = client.post("/api/get-feedback", json={
        "code": "print(5)",
        "language": "python",
        "problem_spec": spec,
        "test_results": test_results,
        "hint_level": 1
    })
    assert res1.status_code == 200
    f1 = res1.json()
    assert f1["hint_level"] == 1
    assert len(f1["active_hint"]) > 0

    # Level 3 hint (approach outline)
    res3 = client.post("/api/get-feedback", json={
        "code": "print(5)",
        "language": "python",
        "problem_spec": spec,
        "test_results": test_results,
        "hint_level": 3
    })
    assert res3.status_code == 200
    f3 = res3.json()
    assert f3["hint_level"] == 3
    assert len(f3["active_hint"]) > 0


def test_sandbox_history():
    res = client.get("/api/sandbox-history?user_id=test_user_1")
    assert res.status_code == 200
    data = res.json()
    assert "attempts" in data
    assert len(data["attempts"]) >= 1
    attempt = data["attempts"][0]
    assert "problem_title" in attempt
    assert "code" in attempt
    assert "mode" in attempt


def test_dynamic_model_tiering_selection():
    from app.llm import get_optimal_gemini_model, is_complex_problem, DEFAULT_FLASH_MODEL, DEFAULT_PRO_MODEL

    # Standard straightforward problem -> Flash model
    simple_prompt = "Given an integer N, return whether it is even or odd."
    assert is_complex_problem(simple_prompt) is False
    assert get_optimal_gemini_model(simple_prompt) == DEFAULT_FLASH_MODEL

    # Complex problem: Dynamic Programming -> Pro model
    dp_prompt = "Find the maximum weight knapsack using dynamic programming with memoization."
    assert is_complex_problem(dp_prompt) is True
    assert get_optimal_gemini_model(dp_prompt) == DEFAULT_PRO_MODEL

    # Complex problem: Large constraints scale N <= 10^5 -> Pro model
    scale_prompt = "Given an array of size up to 10^5, find the longest contiguous subarray sum."
    assert is_complex_problem(scale_prompt) is True
    assert get_optimal_gemini_model(scale_prompt) == DEFAULT_PRO_MODEL

    # Complex problem: Graph Dijkstra -> Pro model
    graph_prompt = "Compute shortest path from node S to T using Dijkstra's algorithm."
    assert is_complex_problem(graph_prompt) is True
    assert get_optimal_gemini_model(graph_prompt) == DEFAULT_PRO_MODEL


def test_time_limit_exceeded_identification():
    spec = {
        "title": "Infinite Loop Challenge",
        "summary": "Process numbers within time limit.",
        "sample_test_cases": [
            {"input": "5", "expected_output": "5"}
        ],
        "hidden_test_cases": []
    }

    # Code that runs infinitely
    infinite_py = """import sys
import time
while True:
    time.sleep(0.1)
"""

    res = client.post("/api/run-code", json={
        "code": infinite_py,
        "language": "python",
        "problem_spec": spec,
        "mode": "run",
        "user_id": "test_user_tle"
    })
    assert res.status_code == 200
    data = res.json()
    test_results = data["test_results"]
    assert test_results["overall_status"] == "timeout"
    assert test_results["timeout_count"] >= 1
    t = test_results["tests"][0]
    assert t["status"] == "timeout"
    assert "Time Limit Exceeded" in t["status_desc"]
    assert "Time Limit Exceeded" in t["stderr"]

    # Verify AI Feedback identifies TLE
    feedback = data["feedback"]
    assert "Time Limit Exceeded" in feedback["summary"] or "Time Limit Exceeded" in feedback.get("error_hint", "")
    hints = feedback.get("hints", {})
    assert "loop" in hints.get("level_1", "").lower() or "progress" in hints.get("level_1", "").lower()
    assert "Simpler Clue" in hints.get("level_2", "") or "loop" in hints.get("level_2", "").lower()


def test_runtime_error_line_number_and_explanation():
    from app.llm import explain_runtime_error

    # Test ZeroDivisionError extraction
    sample_traceback = """Traceback (most recent call last):
  File "solution.py", line 7, in solve
    res = total / count
ZeroDivisionError: division by zero"""

    info = explain_runtime_error(sample_traceback, "python")
    assert info["line_number"] == 7
    assert info["error_type"] == "ZeroDivisionError"
    assert "Line 7:" in info["message"]
    assert "ZeroDivisionError" in info["message"]
    assert "divide by zero" in info["message"]

    # Test execution in sandbox with runtime crash on line 4
    crash_py = """import sys
tokens = sys.stdin.read().split()
# Line 3 comment
x = 10 / 0
"""
    spec = {
        "title": "Division Test",
        "summary": "Read and divide.",
        "sample_test_cases": [{"input": "5", "expected_output": "5"}],
        "hidden_test_cases": []
    }
    res = client.post("/api/run-code", json={
        "code": crash_py,
        "language": "python",
        "problem_spec": spec,
        "mode": "run",
        "user_id": "test_user_crash"
    })
    assert res.status_code == 200
    data = res.json()
    feedback = data["feedback"]
    assert feedback["error_hint"] is not None
    assert "Line 4:" in feedback["error_hint"]
    assert "ZeroDivisionError" in feedback["error_hint"]


def test_chronological_progressive_hints_order():
    spec = {"title": "Arithmetic", "summary": "Sum items"}
    test_results = {
        "all_passed": False,
        "tests": [
            {"status": "failed", "input": "3 5", "expected": "8", "got": "15"}
        ]
    }

    # Request Level 1: Conceptual Invariant
    res1 = client.post("/api/get-feedback", json={
        "code": "print(3 * 5)",
        "language": "python",
        "problem_spec": spec,
        "test_results": test_results,
        "hint_level": 1
    })
    f1 = res1.json()
    assert f1["hint_level"] == 1
    assert "Invariant" in f1["active_hint"] or "Conceptual" in f1["active_hint"] or len(f1["active_hint"]) > 0

    # Request Level 2: Simpler Clue Towards Fix
    res2 = client.post("/api/get-feedback", json={
        "code": "print(3 * 5)",
        "language": "python",
        "problem_spec": spec,
        "test_results": test_results,
        "hint_level": 2
    })
    f2 = res2.json()
    assert f2["hint_level"] == 2
    # Hint 2 is different and simpler, directly guiding towards the fix (e.g. accumulator / comparison / line)
    assert "Simpler Clue" in f2["active_hint"] or "Line" in f2["active_hint"] or len(f2["active_hint"]) > 0
    assert f2["active_hint"] != f1["active_hint"]

    # Request Level 3: Algorithmic Blueprint
    res3 = client.post("/api/get-feedback", json={
        "code": "print(3 * 5)",
        "language": "python",
        "problem_spec": spec,
        "test_results": test_results,
        "hint_level": 3
    })
    f3 = res3.json()
    assert f3["hint_level"] == 3
    assert "Algorithmic Approach" in f3["active_hint"]
    assert f3["active_hint"] != f2["active_hint"]

