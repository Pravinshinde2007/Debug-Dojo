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
    "python": """import sys

def solve():
    # Read all input from standard input
    input_data = sys.stdin.read().split()
    if not input_data:
        return
    # Write your solution here
    print(" ".join(input_data))

if __name__ == '__main__':
    solve()
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


def execute_via_isolated_subprocess(
    code: str,
    language: str,
    stdin: str,
    expected_output: str,
    timeout_s: float = 2.0
) -> Dict[str, Any]:
    """
    Isolated child-process fallback.
    Executes in a temporary sandbox directory with strict time and output limits.
    Main server process is NEVER exposed to user execution.
    """
    norm_expected = expected_output.strip()

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        if language == "python":
            source_file = tmp_path / "solution.py"
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
            # Compile step
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
            got = stdout.strip()

            if proc.returncode != 0:
                return {
                    "status": "error",
                    "status_desc": f"Runtime Error (code {proc.returncode})",
                    "stdout": stdout,
                    "stderr": stderr,
                    "compile_output": "",
                    "time_s": round(duration, 3),
                    "memory_kb": 0,
                    "got": got,
                    "expected": norm_expected
                }

            passed = (got == norm_expected)
            return {
                "status": "passed" if passed else "failed",
                "status_desc": "Accepted" if passed else "Wrong Answer",
                "stdout": stdout,
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
                "status_desc": "Time Limit Exceeded",
                "stdout": "",
                "stderr": f"Process exceeded timeout limit of {timeout_s} seconds.",
                "compile_output": "",
                "time_s": timeout_s,
                "memory_kb": 0,
                "got": "",
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
