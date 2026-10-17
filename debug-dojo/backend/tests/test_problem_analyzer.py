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
