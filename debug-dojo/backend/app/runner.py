"""
Runner module: Spawns isolated child processes to execute learner code against test suites.
Enforces non-negotiable Rule 1 (isolated child process), Rule 2 (hidden tests confidential),
and Rule 3 (exactly one outcome per test).
"""

import sys
import json
import subprocess
import tempfile
import os
from pathlib import Path
from typing import Dict, Any, List

MAX_CODE_BYTES = 16384  # 16KB
PER_TEST_TIMEOUT = 2.0   # 2.0 seconds per test
SUITE_TIMEOUT = 8.0      # 8.0 seconds total

WORKER_SCRIPT = Path(__file__).resolve().parent / "worker.py"


def execute_single_test(code: str, function_name: str, test_def: Dict[str, Any], timeout: float = PER_TEST_TIMEOUT) -> Dict[str, Any]:
    """
    Spawns an isolated child process to execute code against a single test.
    Returns: { outcome, expected, got, stdout, mutated_input, error_msg }
    """
    # Check code size limit (16KB)
    if len(code.encode("utf-8")) > MAX_CODE_BYTES:
        return {
            "outcome": "runtime_error",
            "expected": str(test_def.get("expected", "")),
            "got": "",
            "stdout": "",
            "mutated_input": False,
            "error_msg": "Runtime error: Code size limit exceeded (max 16KB)"
        }

    args = test_def.get("args", [])
    kwargs = test_def.get("kwargs", {})
    expected = test_def.get("expected")

    payload = {
        "code": code,
        "function_name": function_name,
        "args": args,
        "kwargs": kwargs,
    }

    # Use a temporary directory for worker input payload
    with tempfile.TemporaryDirectory() as tmp_dir:
        input_file = Path(tmp_dir) / "payload.json"
        with open(input_file, "w", encoding="utf-8") as f:
            json.dump(payload, f)

        # Non-negotiable Rule 1: Always a separate, restricted child process
        cmd = [sys.executable, str(WORKER_SCRIPT), str(input_file)]

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            raw_stdout = proc.stdout.strip()
            
            if not raw_stdout:
                # Process crashed or was terminated
                return {
                    "outcome": "runtime_error",
                    "expected": str(expected),
                    "got": "",
                    "stdout": "",
                    "mutated_input": False,
                    "error_msg": proc.stderr.strip() or "Runtime error: Child process terminated unexpectedly"
                }

            result_data = json.loads(raw_stdout)
            runtime_err = result_data.get("runtime_error")
            output_limit_hit = result_data.get("output_limit_hit", False)
            mutated_input = result_data.get("mutated_input", False)
            stdout = result_data.get("stdout", "")
            return_val = result_data.get("return_val")

            if output_limit_hit:
                return {
                    "outcome": "runtime_error",
                    "expected": str(expected),
                    "got": str(return_val) if return_val is not None else "",
                    "stdout": stdout,
                    "mutated_input": mutated_input,
                    "error_msg": "Runtime error: Output limit exceeded (max 4KB)"
                }

            if runtime_err:
                return {
                    "outcome": "runtime_error",
                    "expected": str(expected),
                    "got": str(return_val) if return_val is not None else "",
                    "stdout": stdout,
                    "mutated_input": mutated_input,
                    "error_msg": runtime_err
                }

            # Check argument mutation restriction if prohibited
            if mutated_input and test_def.get("prohibit_mutation", True):
                return {
                    "outcome": "wrong_output",
                    "expected": str(expected),
                    "got": str(return_val),
                    "stdout": stdout,
                    "mutated_input": True,
                    "error_msg": "Function illegally mutated input argument"
                }

            # Compare return value with expected
            if return_val == expected:
                outcome = "passed"
            else:
                outcome = "wrong_output"

            return {
                "outcome": outcome,
                "expected": str(expected),
                "got": str(return_val) if return_val is not None else "None",
                "stdout": stdout,
                "mutated_input": mutated_input,
                "return_val": return_val,
                "error_msg": None
            }

        except subprocess.TimeoutExpired:
            # Rule 3: timeout outcome
            return {
                "outcome": "timeout",
                "expected": str(expected),
                "got": "",
                "stdout": "",
                "mutated_input": False,
                "error_msg": f"Execution timed out (exceeded {timeout}s limit)"
            }
        except Exception as ex:
            return {
                "outcome": "runtime_error",
                "expected": str(expected),
                "got": "",
                "stdout": "",
                "mutated_input": False,
                "error_msg": f"Sandbox execution error: {str(ex)}"
            }


def run_submission(code: str, challenge: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executes learner code against visible and hidden test suites.
    Enforces Rule 2 (hidden tests strictly confidential).
    """
    function_name = challenge.get("function_name")
    if not function_name:
        # Infer function name from starter_code or id
        starter = challenge.get("starter_code", "")
        if "def " in starter:
            function_name = starter.split("def ")[1].split("(")[0].strip()
        else:
            function_name = challenge.get("id", "").replace("-", "_")

    visible_tests = challenge.get("visible_tests", [])
    hidden_tests = challenge.get("hidden_tests", [])

    visible_results = []
    hidden_results = []
    detailed_test_data = []  # Used internally by tagger, never exposed to user

    all_passed = True

    # 1. Run Visible Tests
    for idx, t in enumerate(visible_tests, 1):
        res = execute_single_test(code, function_name, t)
        if res["outcome"] != "passed":
            all_passed = False

        visible_results.append({
            "test": idx,
            "call": t.get("call", f"{function_name}()"),
            "expected": str(t.get("expected", "")),
            "got": res["got"],
            "outcome": res["outcome"]
        })

        detailed_test_data.append({
            "test": idx,
            "is_hidden": False,
            "call": t.get("call", ""),
            "args": t.get("args", []),
            "expected": t.get("expected"),
            "got": res.get("return_val"),
            "stdout": res.get("stdout", ""),
            "outcome": res["outcome"],
            "mutated_input": res.get("mutated_input", False),
            "kind": t.get("kind", ""),
            "error_msg": res.get("error_msg")
        })

    # 2. Run Hidden Tests (Strict Confidentiality Guard)
    for idx, t in enumerate(hidden_tests, len(visible_results) + 1):
        res = execute_single_test(code, function_name, t)
        if res["outcome"] != "passed":
            all_passed = False

        # Rule 2: Never reveal hidden test's input, expected, got, or exception message!
        hidden_results.append({
            "test": idx,
            "outcome": res["outcome"]
        })

        detailed_test_data.append({
            "test": idx,
            "is_hidden": True,
            "call": t.get("call", ""),
            "args": t.get("args", []),
            "expected": t.get("expected"),
            "got": res.get("return_val"),
            "stdout": res.get("stdout", ""),
            "outcome": res["outcome"],
            "mutated_input": res.get("mutated_input", False),
            "kind": t.get("kind", ""),  # e.g. "a case where k is larger than the list"
            "error_msg": res.get("error_msg")
        })

    return {
        "visible": visible_results,
        "hidden": hidden_results,
        "all_passed": all_passed,
        "_detailed_data": detailed_test_data  # Internal only for tagger / explain
    }
