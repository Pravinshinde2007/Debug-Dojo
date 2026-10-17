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
                    "error_msg": runtime_err,
                    "error_type": result_data.get("error_type") or "RuntimeError",
                    "error_line": result_data.get("error_line")
                }

            # Check argument mutation restriction if prohibited
            if mutated_input and test_def.get("prohibit_mutation", True):
                return {
                    "outcome": "wrong_output",
                    "expected": str(expected),
                    "got": str(return_val),
                    "stdout": stdout,
                    "mutated_input": True,
                    "error_msg": "Function illegally mutated input argument",
                    "error_type": None,
                    "error_line": None
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
                "error_msg": None,
                "error_type": None,
                "error_line": None
            }

        except subprocess.TimeoutExpired:
            # Rule 3: timeout outcome
            return {
                "outcome": "timeout",
                "expected": str(expected),
                "got": "",
                "stdout": "",
                "mutated_input": False,
                "error_msg": f"Execution timed out (exceeded {timeout}s limit)",
                "error_type": "TimeoutError",
                "error_line": None
            }
        except Exception as ex:
            return {
                "outcome": "runtime_error",
                "expected": str(expected),
                "got": "",
                "stdout": "",
                "mutated_input": False,
                "error_msg": f"Sandbox execution error: {str(ex)}",
                "error_type": type(ex).__name__,
                "error_line": getattr(ex, "lineno", None)
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
    first_error = None
    first_failed_test = None
    has_timeout = False
    has_runtime = False
    has_wrong = False

    # 1. Run Visible Tests
    for idx, t in enumerate(visible_tests, 1):
        res = execute_single_test(code, function_name, t)
        if res["outcome"] != "passed":
            all_passed = False
            if not first_failed_test:
                first_failed_test = {
                    "test": idx,
                    "call": t.get("call", f"{function_name}()"),
                    "expected": str(t.get("expected", "")),
                    "got": res["got"],
                    "outcome": res["outcome"],
                    "kind": t.get("kind", "")
                }
            if res["outcome"] == "timeout":
                has_timeout = True
            elif res["outcome"] == "runtime_error":
                has_runtime = True
                if not first_error:
                    first_error = {
                        "error_type": res.get("error_type") or "RuntimeError",
                        "error_line": res.get("error_line"),
                        "error_msg": res.get("error_msg")
                    }
            else:
                has_wrong = True

        visible_results.append({
            "test": idx,
            "call": t.get("call", f"{function_name}()"),
            "expected": str(t.get("expected", "")),
            "got": res["got"],
            "outcome": res["outcome"],
            "error_msg": res.get("error_msg"),
            "error_type": res.get("error_type"),
            "error_line": res.get("error_line")
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
            "error_msg": res.get("error_msg"),
            "error_type": res.get("error_type"),
            "error_line": res.get("error_line")
        })

    # 2. Run Hidden Tests (Strict Confidentiality Guard)
    for idx, t in enumerate(hidden_tests, len(visible_results) + 1):
        res = execute_single_test(code, function_name, t)
        if res["outcome"] != "passed":
            all_passed = False
            if not first_failed_test:
                first_failed_test = {
                    "test": idx,
                    "call": f"{function_name}(...)",
                    "expected": "confidential",
                    "got": "confidential",
                    "outcome": res["outcome"],
                    "kind": t.get("kind", "")
                }
            if res["outcome"] == "timeout":
                has_timeout = True
            elif res["outcome"] == "runtime_error":
                has_runtime = True
                if not first_error:
                    first_error = {
                        "error_type": res.get("error_type") or "RuntimeError",
                        "error_line": res.get("error_line"),
                        "error_msg": res.get("error_msg")
                    }
            else:
                has_wrong = True

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
            "error_msg": res.get("error_msg"),
            "error_type": res.get("error_type"),
            "error_line": res.get("error_line")
        })

    if all_passed:
        overall_outcome = "passed"
    elif has_timeout:
        overall_outcome = "timeout"
    elif has_runtime:
        overall_outcome = "runtime error"
    else:
        overall_outcome = "wrong output"

    return {
        "visible": visible_results,
        "hidden": hidden_results,
        "all_passed": all_passed,
        "overall_outcome": overall_outcome,
        "first_error": first_error,
        "first_failed_test": first_failed_test,
        "_detailed_data": detailed_test_data  # Internal only for tagger / explain
    }


def run_custom_code(code: str, timeout: float = PER_TEST_TIMEOUT) -> Dict[str, Any]:
    """
    Executes learner's custom arbitrary Python code in an isolated child process sandbox.
    Enforces Rule 1 (isolated child process) and returns execution output, error type,
    error line, and stdout.
    """
    if len(code.encode("utf-8")) > MAX_CODE_BYTES:
        return {
            "outcome": "runtime_error",
            "error_type": "MemoryError",
            "error_line": None,
            "error_msg": "Code size limit exceeded (max 16KB)",
            "stdout": "",
            "return_val": None,
        }

    # Pre-check AST syntax
    try:
        compile(code, "<string>", "exec")
    except SyntaxError as syn_err:
        return {
            "outcome": "syntax_error",
            "error_type": type(syn_err).__name__,
            "error_line": syn_err.lineno,
            "error_msg": str(syn_err),
            "stdout": "",
            "return_val": None,
        }
    except Exception as ast_err:
        return {
            "outcome": "syntax_error",
            "error_type": type(ast_err).__name__,
            "error_line": getattr(ast_err, "lineno", None),
            "error_msg": str(ast_err),
            "stdout": "",
            "return_val": None,
        }

    payload = {
        "code": code,
        "function_name": "",
        "args": [],
        "kwargs": {},
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        input_file = Path(tmp_dir) / "payload.json"
        with open(input_file, "w", encoding="utf-8") as f:
            json.dump(payload, f)

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
                return {
                    "outcome": "runtime_error",
                    "error_type": "ProcessTerminated",
                    "error_line": None,
                    "error_msg": proc.stderr.strip() or "Child process terminated unexpectedly",
                    "stdout": "",
                    "return_val": None,
                }

            result_data = json.loads(raw_stdout)
            runtime_err = result_data.get("runtime_error")
            output_limit_hit = result_data.get("output_limit_hit", False)
            stdout = result_data.get("stdout", "")
            return_val = result_data.get("return_val")
            err_type = result_data.get("error_type")
            err_line = result_data.get("error_line")

            if output_limit_hit:
                return {
                    "outcome": "runtime_error",
                    "error_type": "OutputLimitExceeded",
                    "error_line": err_line,
                    "error_msg": "Output limit exceeded (max 4KB)",
                    "stdout": stdout,
                    "return_val": return_val,
                }

            if runtime_err:
                return {
                    "outcome": "runtime_error",
                    "error_type": err_type or "RuntimeError",
                    "error_line": err_line,
                    "error_msg": runtime_err,
                    "stdout": stdout,
                    "return_val": return_val,
                }

            return {
                "outcome": "passed",
                "error_type": None,
                "error_line": None,
                "error_msg": None,
                "stdout": stdout,
                "return_val": return_val,
            }

        except subprocess.TimeoutExpired:
            return {
                "outcome": "timeout",
                "error_type": "TimeoutError",
                "error_line": None,
                "error_msg": f"Execution timed out (exceeded {timeout}s limit - possible infinite loop)",
                "stdout": "",
                "return_val": None,
            }
        except Exception as ex:
            return {
                "outcome": "runtime_error",
                "error_type": "SandboxError",
                "error_line": None,
                "error_msg": f"Sandbox execution error: {str(ex)}",
                "stdout": "",
                "return_val": None,
            }
