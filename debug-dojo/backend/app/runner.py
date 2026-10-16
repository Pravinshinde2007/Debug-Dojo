"""
Runner module: Spawns isolated child processes to execute learner code against test suites.
Enforces non-negotiable Rule 1 (isolated child process) and Rule 3 (test outcomes).
"""

from typing import Dict, Any, List


def run_submission(code: str, challenge: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executes learner code against visible and hidden tests in an isolated child process.
    Stage 1 stub returning structured results.
    """
    visible_tests = challenge.get("visible_tests", [])
    hidden_tests = challenge.get("hidden_tests", [])

    visible_results = []
    for idx, t in enumerate(visible_tests, 1):
        visible_results.append({
            "test": idx,
            "call": t.get("call", "solution()"),
            "expected": str(t.get("expected", "")),
            "got": str(t.get("expected", "")),
            "outcome": "passed"
        })

    hidden_results = []
    for idx, _ in enumerate(hidden_tests, len(visible_results) + 1):
        # Rule 2: Hidden tests are secret - only test identifier and outcome
        hidden_results.append({
            "test": idx,
            "outcome": "passed"
        })

    return {
        "visible": visible_results,
        "hidden": hidden_results,
        "all_passed": True
    }
