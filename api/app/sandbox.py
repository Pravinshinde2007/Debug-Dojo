"""
Isolated Code Execution Sandbox.
Executes code strictly in isolated environments (Judge0 API, Docker, or isolated child process).
NEVER runs untrusted code in the main server process.
"""

import os
import sys
import json
import base64
import time
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional
import httpx

JUDGE0_URL = os.environ.get("JUDGE0_API_URL", "https://ce.judge0.com").rstrip("/")
JUDGE0_KEY = os.environ.get("JUDGE0_API_KEY", "")
JUDGE0_HOST = os.environ.get("JUDGE0_API_HOST", "")

# Standard Judge0 Language IDs
LANGUAGE_IDS = {
    "python": 71,       # Python (3.8.1)
    "javascript": 63,   # JavaScript (Node.js 12.14.0)
    "cpp": 54,          # C++ (GCC 9.2.0)
    "java": 62          # Java (OpenJDK 13.0.1)
}

STARTER_TEMPLATES = {
    "python": """def two_sum(nums: list[int], target: int) -> list[int]:
    \"\"\"
    Given an array of integers nums and an integer target,
    return indices of the two numbers such that they add up to target.
    \"\"\"
    # Write your solution here
    pass
""",
    "javascript": """const fs = require('fs');

function solve() {
    const input = fs.readFileSync(0, 'utf-8').trim();
    if (!input) return;
    // Write your solution here
    console.log(input);
}

solve();
""",
    "cpp": """#include <iostream>
#include <string>
#include <vector>

using namespace std;

int main() {
    ios_base::sync_with_stdio(false);
    cin.tie(NULL);
    
    // Write your solution here
    string s;
    while (cin >> s) {
        cout << s << " ";
    }
    return 0;
}
""",
    "java": """import java.util.Scanner;

public class Main {
    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);
        // Write your solution here
        while (sc.hasNext()) {
            System.out.print(sc.next() + " ");
        }
    }
}
"""
}

WORKER_SCRIPT = Path(__file__).resolve().parent / "worker.py"


def _headers() -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if JUDGE0_KEY:
        headers["X-RapidAPI-Key"] = JUDGE0_KEY
        if JUDGE0_HOST:
            headers["X-RapidAPI-Host"] = JUDGE0_HOST
    return headers


async def execute_via_judge0(
    code: str,
    language: str,
    stdin: str,
    expected_output: str,
    timeout_s: float = 2.0,
    memory_limit_kb: int = 128000
) -> Dict[str, Any]:
    """
    Submits code to Judge0 API with strict CPU and memory limits.
    """
    lang_id = LANGUAGE_IDS.get(language.lower(), 71)
    url = f"{JUDGE0_URL}/submissions?base64_encoded=true&wait=true"
    
    b64_source = base64.b64encode(code.encode("utf-8")).decode("ascii")
    b64_stdin = base64.b64encode(stdin.encode("utf-8")).decode("ascii")
    b64_expected = base64.b64encode(expected_output.encode("utf-8")).decode("ascii")

    payload = {
        "source_code": b64_source,
        "language_id": lang_id,
        "stdin": b64_stdin,
        "expected_output": b64_expected,
        "cpu_time_limit": timeout_s,
        "memory_limit": memory_limit_kb,
        "wall_time_limit": timeout_s * 2
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(url, json=payload, headers=_headers())
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"Judge0 API returned {resp.status_code}: {resp.text}")
        
        data = resp.json()
        status_info = data.get("status", {})
        status_id = status_info.get("id", 0)
        status_desc = status_info.get("description", "Unknown")

        def _decode(b64_val: Optional[str]) -> str:
            if not b64_val:
                return ""
            try:
                return base64.b64decode(b64_val).decode("utf-8", errors="replace")
            except Exception:
                return str(b64_val)

        stdout = _decode(data.get("stdout"))
        stderr = _decode(data.get("stderr"))
        compile_output = _decode(data.get("compile_output"))
        time_s = float(data.get("time") or 0.0)
        memory_kb = int(data.get("memory") or 0)

        # Status mapping in Judge0:
        # 3: Accepted
        # 4: Wrong Answer
        # 5: Time Limit Exceeded
        # 6: Compilation Error
        # 7..12: Runtime Error
        if status_id == 3:
            outcome = "passed"
        elif status_id == 4:
            outcome = "failed"
        elif status_id == 5:
            outcome = "timeout"
            status_desc = "Time Limit Exceeded (TLE)"
            if not stderr:
                stderr = f"Time Limit Exceeded (TLE): Process exceeded CPU time limit of {timeout_s}s. Check for infinite loops or inefficient time complexity (O(N^2) or higher)."
        elif status_id == 6:
            outcome = "error"
            stderr = compile_output or stderr
        else:
            outcome = "error"

        return {
            "status": outcome,
            "status_desc": status_desc,
            "stdout": stdout,
            "stderr": stderr,
            "compile_output": compile_output,
            "time_s": time_s,
            "memory_kb": memory_kb,
            "got": stdout.strip(),
            "expected": expected_output.strip()
        }


def _check_match(got: str, expected: str) -> bool:
    g = got.strip()
    e = expected.strip()
    if g == e:
        return True
    if g.lower() in ("true", "false") and e.lower() in ("true", "false"):
        return g.lower() == e.lower()
    try:
        import ast
        g_val = ast.literal_eval(g)
        e_val = ast.literal_eval(e)
        if g_val == e_val:
            return True
        if isinstance(g_val, (list, tuple)) and isinstance(e_val, (list, tuple)):
            if sorted(list(g_val)) == sorted(list(e_val)):
                return True
    except Exception:
        pass
    import re
    if re.sub(r'\s+', '', g) == re.sub(r'\s+', '', e):
        return True
    return False


def _build_python_harness(user_code: str, raw_stdin: str) -> tuple:
    """
    Constructs an isolated execution script that wraps user code,
    executing their LeetCode-style function or class Solution,
    while capturing outputs and mapping traceback line numbers back to user code.
    Returns (harness_code, user_code_start_line).
    """
    header = "import sys, io, json, ast, re, traceback\n\n"
    user_start_line = 3  # Line where user_code begins
    
    footer = f"""
def _normalize_result(val):
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, (list, tuple)):
        return json.dumps(list(val))
    if isinstance(val, dict):
        return json.dumps(val, sort_keys=True)
    if val is None:
        return ""
    return str(val)

def _extract_user_callable():
    if "Solution" in globals() and isinstance(globals()["Solution"], type):
        inst = globals()["Solution"]()
        methods = [m for m in dir(inst) if not m.startswith("_") and callable(getattr(inst, m))]
        if methods:
            return getattr(inst, methods[0])
    internal = {{
        "_normalize_result", "_extract_user_callable", "_parse_args",
        "sys", "io", "json", "ast", "re", "traceback"
    }}
    candidates = []
    for name, obj in list(globals().items()):
        if name not in internal and not name.startswith("_") and callable(obj):
            if hasattr(obj, "__code__"):
                candidates.append((obj.__code__.co_firstlineno, obj))
    if candidates:
        candidates.sort(key=lambda x: x[0])
        return candidates[-1][1]
    return None

def _parse_args(raw):
    if not raw:
        return []
    inp = str(raw).strip()
    try:
        val = json.loads(inp)
        if isinstance(val, list):
            return val
        return [val]
    except Exception:
        pass
    try:
        parts = re.split(r'\\s*,\\s*(?=[a-zA-Z_]\\w*\\s*=)', inp)
        vals = []
        for part in parts:
            if '=' in part:
                _, v = part.split('=', 1)
                vals.append(ast.literal_eval(v.strip()))
        if vals:
            return vals
    except Exception:
        pass
    try:
        tup = ast.literal_eval(f"({{inp}},)")
        if tup:
            return list(tup)
    except Exception:
        pass
    lines = [l.strip() for l in inp.split('\\n') if l.strip()]
    parsed = []
    for l in lines:
        try:
            parsed.append(ast.literal_eval(l))
        except Exception:
            try:
                nums = [int(x) for x in l.split()]
                parsed.append(nums if len(nums) > 1 else nums[0])
            except Exception:
                parsed.append(l)
    return parsed

if __name__ == '__main__':
    raw_input_str = {repr(raw_stdin)}
    target = _extract_user_callable()
    
    captured_stdout = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = captured_stdout
    
    ret_val = None
    has_ret = False
    try:
        if target is not None:
            args = _parse_args(raw_input_str)
            if isinstance(args, list):
                ret_val = target(*args)
            elif isinstance(args, dict):
                ret_val = target(**args)
            else:
                ret_val = target(args)
            has_ret = True
    finally:
        sys.stdout = old_stdout

    printed = captured_stdout.getvalue().strip()
    print("===DEBUG_DOJO_RESULT===")
    if has_ret and ret_val is not None:
        print(_normalize_result(ret_val))
    elif printed:
        print(printed)
    else:
        print("")
"""
    return (header + user_code + footer, user_start_line)


def execute_via_isolated_subprocess(
    code: str,
    language: str,
    stdin: str,
    expected_output: str,
    timeout_s: float = 2.0
) -> Dict[str, Any]:
    """
    Isolated child-process execution sandbox.
    Supports LeetCode-style Python functions and standalone scripts.
    Main server process is NEVER exposed to user execution.
    """
    norm_expected = expected_output.strip()
    user_start_line = 1

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        if language == "python":
            source_file = tmp_path / "solution.py"
            # If code defines a function or class Solution, wrap in harness
            if "def " in code or "class " in code:
                harness_code, user_start_line = _build_python_harness(code, stdin)
                source_file.write_text(harness_code, encoding="utf-8")
            else:
                source_file.write_text(code, encoding="utf-8")
            cmd = [sys.executable, str(source_file)]
        elif language == "javascript":
            source_file = tmp_path / "solution.js"
            source_file.write_text(code, encoding="utf-8")
            cmd = ["node", str(source_file)]
        elif language == "cpp":
            source_file = tmp_path / "solution.cpp"
            binary_file = tmp_path / ("solution.exe" if os.name == "nt" else "solution")
            source_file.write_text(code, encoding="utf-8")
            compile_proc = subprocess.run(
                ["g++", "-O2", str(source_file), "-o", str(binary_file)],
                capture_output=True,
                text=True,
                timeout=5.0
            )
            if compile_proc.returncode != 0:
                return {
                    "status": "error",
                    "status_desc": "Compilation Error",
                    "stdout": "",
                    "stderr": compile_proc.stderr,
                    "compile_output": compile_proc.stderr,
                    "time_s": 0.0,
                    "memory_kb": 0,
                    "got": "",
                    "expected": norm_expected
                }
            cmd = [str(binary_file)]
        elif language == "java":
            source_file = tmp_path / "Main.java"
            source_file.write_text(code, encoding="utf-8")
            compile_proc = subprocess.run(
                ["javac", str(source_file)],
                capture_output=True,
                text=True,
                timeout=5.0
            )
            if compile_proc.returncode != 0:
                return {
                    "status": "error",
                    "status_desc": "Compilation Error",
                    "stdout": "",
                    "stderr": compile_proc.stderr,
                    "compile_output": compile_proc.stderr,
                    "time_s": 0.0,
                    "memory_kb": 0,
                    "got": "",
                    "expected": norm_expected
                }
            cmd = ["java", "-cp", str(tmp_path), "Main"]
        else:
            raise ValueError(f"Unsupported language: {language}")

        start_time = time.time()
        try:
            proc = subprocess.run(
                cmd,
                input=stdin,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                cwd=str(tmp_path)
            )
            duration = time.time() - start_time
            stdout = proc.stdout[:4096]
            stderr = proc.stderr[:4096]

            # Parse harness result if present
            if "===DEBUG_DOJO_RESULT===" in stdout:
                parts = stdout.split("===DEBUG_DOJO_RESULT===")
                user_stdout = parts[0].strip()
                got = parts[1].strip()
            else:
                user_stdout = stdout.strip()
                got = stdout.strip()

            if proc.returncode != 0:
                # Extract line number from traceback
                import re
                err_line = None
                lines_m = re.findall(r'File "[^"]+", line (\d+)', stderr)
                if lines_m:
                    raw_l = int(lines_m[-1])
                    user_l = raw_l - (user_start_line - 1)
                    if 1 <= user_l <= len(code.splitlines()):
                        err_line = user_l
                    else:
                        err_line = max(1, user_l)

                err_type_m = re.search(r'([A-Z]\w+Error): (.*)', stderr)
                err_type = err_type_m.group(1) if err_type_m else "RuntimeError"
                err_msg = err_type_m.group(2) if err_type_m else "Process terminated with error"

                status_desc = f"Runtime Error ({err_type} at line {err_line})" if err_line else f"Runtime Error ({err_type})"
                clean_stderr = f"Line {err_line}: {err_type} — {err_msg}\n{stderr}" if err_line else stderr

                return {
                    "status": "error",
                    "status_desc": status_desc,
                    "stdout": user_stdout,
                    "stderr": clean_stderr,
                    "compile_output": "",
                    "time_s": round(duration, 3),
                    "memory_kb": 0,
                    "got": got or f"[{err_type} on line {err_line or '?'}]",
                    "expected": norm_expected,
                    "error_line": err_line,
                    "error_type": err_type
                }

            passed = _check_match(got, norm_expected)
            return {
                "status": "passed" if passed else "failed",
                "status_desc": "Accepted" if passed else "Wrong Answer",
                "stdout": user_stdout,
                "stderr": stderr,
                "compile_output": "",
                "time_s": round(duration, 3),
                "memory_kb": 0,
                "got": got,
                "expected": norm_expected
            }
        except subprocess.TimeoutExpired:
            return {
                "status": "timeout",
                "status_desc": "Time Limit Exceeded (TLE)",
                "stdout": "",
                "stderr": f"Time Limit Exceeded (TLE): Process exceeded allowable time limit of {timeout_s} seconds. This typically indicates an infinite loop (e.g., missing loop variable increment) or quadratic/exponential complexity O(N^2) on large input cases.",
                "compile_output": "",
                "time_s": timeout_s,
                "memory_kb": 0,
                "got": "[Execution Timed Out]",
                "expected": norm_expected
            }
        except Exception as e:
            return {
                "status": "error",
                "status_desc": "Execution Failed",
                "stdout": "",
                "stderr": str(e),
                "compile_output": "",
                "time_s": 0.0,
                "memory_kb": 0,
                "got": "",
                "expected": norm_expected
            }


async def run_single_test_isolated(
    code: str,
    language: str,
    stdin: str,
    expected_output: str,
    timeout_s: float = 2.0
) -> Dict[str, Any]:
    """
    Attempts Judge0 execution first. If Judge0 is unconfigured or unreachable,
    falls back cleanly to isolated child-process execution.
    """
    try:
        # Check if Judge0 is active and responding
        res = await execute_via_judge0(code, language, stdin, expected_output, timeout_s)
        return res
    except Exception:
        # Isolated child-process fallback
        return execute_via_isolated_subprocess(code, language, stdin, expected_output, timeout_s)


async def execute_test_suite(
    code: str,
    language: str,
    tests: List[Dict[str, Any]],
    timeout_per_test: float = 2.0
) -> Dict[str, Any]:
    """
    Runs a list of tests in isolation against user code.
    Returns structured pass/fail results for each test.
    """
    results = []
    passed_count = 0
    failed_count = 0
    error_count = 0
    timeout_count = 0

    for idx, t in enumerate(tests, start=1):
        test_in = str(t.get("input", ""))
        test_exp = str(t.get("expected_output", t.get("expected", "")))
        
        exec_res = await run_single_test_isolated(
            code=code,
            language=language,
            stdin=test_in,
            expected_output=test_exp,
            timeout_s=timeout_per_test
        )

        status = exec_res.get("status", "error")
        if status == "passed":
            passed_count += 1
        elif status == "failed":
            failed_count += 1
        elif status == "timeout":
            timeout_count += 1
        else:
            error_count += 1

        results.append({
            "test_id": idx,
            "input": test_in,
            "expected": test_exp.strip(),
            "got": exec_res.get("got", ""),
            "stdout": exec_res.get("stdout", ""),
            "stderr": exec_res.get("stderr", ""),
            "compile_output": exec_res.get("compile_output", ""),
            "status": status,
            "status_desc": exec_res.get("status_desc", ""),
            "time_s": exec_res.get("time_s", 0.0),
            "memory_kb": exec_res.get("memory_kb", 0),
            "is_hidden": bool(t.get("is_hidden", False))
        })

    all_passed = (passed_count == len(tests) and len(tests) > 0)

    if all_passed:
        overall_status = "passed"
    elif timeout_count > 0:
        overall_status = "timeout"
    elif error_count > 0:
        overall_status = "runtime_error"
    else:
        overall_status = "wrong_answer"

    return {
        "all_passed": all_passed,
        "total_tests": len(tests),
        "passed_count": passed_count,
        "failed_count": failed_count,
        "error_count": error_count,
        "timeout_count": timeout_count,
        "overall_status": overall_status,
        "tests": results
    }
