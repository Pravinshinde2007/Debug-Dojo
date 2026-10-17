"""
AI Feedback Engine.
Provides case-by-case diagnosis, error hints, logic explanations,
time/space complexity tips, and progressive leak-guarded hint levels.
Features free-tier Gemini API with dynamic model tiering (Pro for complex, Flash for standard),
Time Limit Exceeded (TLE) detection, runtime error line number extraction,
and strict chronological progressive hints.
"""

import os
import re
import json
from typing import Dict, Any, Optional, List
import httpx

from .llm import (
    leak_guard,
    get_gemini_api_key,
    get_optimal_gemini_model,
    explain_runtime_error,
    DEFAULT_FLASH_MODEL,
    DEFAULT_PRO_MODEL,
    FLASH_FALLBACKS,
    PRO_FALLBACKS
)

FEEDBACK_SYSTEM_PROMPT = """You are an encouraging and pedagogically rigorous coding coach.
You help learners understand their mistakes WITHOUT giving away the complete solution code.
Analyze the user's submitted code, the problem specification, the test results, and the requested hint level.

Return a STRICT JSON object with this exact schema:
{
  "summary": "1-2 sentence overall assessment of the attempt",
  "error_hint": "If runtime/syntax error: specify the line number and a concise 1-2 sentence explanation of the specific error (e.g. Line 7: ZeroDivisionError — You are dividing by a variable that evaluates to 0...). If Time Limit Exceeded (TLE): explain infinite loops or O(N^2) complexity. Otherwise null.",
  "logic_explanation": "If wrong answer: explain WHERE the logic is wrong and why (e.g. accumulator initialization, loop boundary, or comparison operator). Otherwise null.",
  "failing_case": {
    "input": "...",
    "expected": "...",
    "got": "..."
  },
  "complexity_tip": "If all tests pass: time and space complexity analysis (e.g. O(N) time, O(1) space) and optimization tips. Otherwise brief note on efficiency.",
  "hints": {
    "level_1": "Broad conceptual nudge — high-level principle, invariant, or question to reflect on.",
    "level_2": "Simpler and distinctly DIFFERENT clue pointing directly towards the fix (e.g. point to the specific line or calculation that went wrong and simply state what needs to change).",
    "level_3": "High-level algorithmic approach outline — step-by-step procedural steps to construct the correct solution without giving away copy-paste code."
  }
}

RULES:
1. Strict chronological hint progression:
   - Hint 1 must be conceptual.
   - Hint 2 must be distinctly simpler, different, and point directly towards what to fix (e.g. line number and operator/accumulator adjustment).
   - Hint 3 must provide the step-by-step algorithmic blueprint.
2. If the failure is Time Limit Exceeded (TLE):
   - Highlight whether an infinite loop or high algorithmic time complexity (e.g. O(N^2) on large inputs) is the cause.
3. If runtime error:
   - Identify the exact line number from the traceback and provide a friendly 1-2 sentence explanation.
4. Never provide full working code blocks.
5. Output raw JSON only.
"""


def _generate_rule_based_feedback(
    code: str,
    language: str,
    problem_spec: Dict[str, Any],
    test_results: Dict[str, Any],
    hint_level: int = 1
) -> Dict[str, Any]:
    """Offline rule-based fallback when Gemini API is unconfigured or unreachable."""
    all_passed = test_results.get("all_passed", False)
    tests = test_results.get("tests", [])

    first_failed = None
    first_error = None
    first_timeout = None

    for t in tests:
        status = t.get("status")
        if status == "timeout" and not first_timeout:
            first_timeout = t
        elif status == "error" and not first_error:
            first_error = t
        elif status == "failed" and not first_failed:
            first_failed = t

    # 1. ALL PASSED
    if all_passed:
        return {
            "summary": "Solved! All test cases passed successfully. Excellent work!",
            "error_hint": None,
            "logic_explanation": None,
            "failing_case": None,
            "complexity_tip": "Optimal Performance: Your solution achieves linear time complexity O(N) with O(1) auxiliary space.",
            "hints": {
                "level_1": "Great job! Try to see if you can solve it with fewer lines or zero extra memory allocations.",
                "level_2": "Simpler Clue: Consider in-place operations or generator expressions if dealing with arrays or strings.",
                "level_3": "Algorithmic Approach: Benchmark your solution against extreme scale constraints (N = 10^5) to verify runtime bounds."
            }
        }

    # 2. TIME LIMIT EXCEEDED (TLE)
    if first_timeout or test_results.get("overall_status") == "timeout":
        t = first_timeout or tests[0] if tests else {}
        timeout_val = t.get("time_s", 2.0)
        return {
            "summary": "Time Limit Exceeded (TLE): Your code did not finish execution within the allowed time limit.",
            "error_hint": f"Time Limit Exceeded (TLE): Execution exceeded {timeout_val}s. This usually indicates an infinite loop (e.g. while condition never terminating) or an algorithm with quadratic/exponential complexity O(N^2) on large input cases.",
            "logic_explanation": None,
            "failing_case": {
                "input": t.get("input", ""),
                "expected": t.get("expected", ""),
                "got": "[Execution Timed Out]"
            },
            "complexity_tip": "Reduce asymptotic complexity: replace nested O(N^2) loops with an O(N) hash map or two-pointer technique.",
            "hints": {
                "level_1": "Loop Termination Invariant: Check all loop conditions to verify that every loop iteration is guaranteed to make progress towards stopping.",
                "level_2": "Simpler Clue: Look at your while or for loop control variables. Verify that loop indices increment in every branch, or avoid nested loops scanning the entire collection.",
                "level_3": "Algorithmic Approach: 1. If loops terminate, the constraint size requires O(N) or O(N log N). 2. Store seen values in a hash set/dict for O(1) lookups. 3. Traverse in a single pass."
            }
        }

    # 3. RUNTIME / COMPILATION ERROR
    if first_error:
        stderr = first_error.get("stderr") or first_error.get("compile_output") or "Runtime error"
        err_info = explain_runtime_error(stderr, language, code)
        line_num = err_info.get("line_number")
        error_type = err_info.get("error_type", "RuntimeError")
        err_msg = err_info.get("message")

        line_str = f"Line {line_num}" if line_num else "your code"

        return {
            "summary": f"Your code encountered a runtime error during execution ({first_error.get('status_desc', error_type)}).",
            "error_hint": err_msg,
            "logic_explanation": None,
            "failing_case": {
                "input": first_error.get("input", ""),
                "expected": first_error.get("expected", ""),
                "got": first_error.get("got", "") or "[Error: Process terminated]"
            },
            "complexity_tip": "Fix runtime exceptions first before analyzing time or space complexity.",
            "hints": {
                "level_1": f"Inspect the operation on {line_str}: ensure variables are initialized with valid values and types before executing this line.",
                "level_2": f"Simpler Clue: On {line_str}, add a guard check (e.g. check for non-zero divisor, non-empty list, or valid key) to prevent the {error_type}.",
                "level_3": f"Algorithmic Approach: Structure your solution with defensive entry checks: validate input lengths and parse all tokens before accessing specific indices."
            }
        }

    # 4. WRONG ANSWER / LOGIC MISMATCH
    if first_failed:
        inp = first_failed.get("input", "")
        exp = first_failed.get("expected", "")
        got = first_failed.get("got", "")
        is_hidden = first_failed.get("is_hidden", False)

        # Logic diagnosis
        diagnosis = "Your logic produces a mismatch against the expected result."
        if not got:
            diagnosis = "Your function returned empty or did not print the expected output to stdout."
        elif len(got) != len(exp):
            diagnosis = f"Output length mismatch: generated {len(got)} characters but expected {len(exp)}."
        else:
            diagnosis = "Check off-by-one errors or edge cases (such as zero, empty sequences, or negative values)."

        # Try to find key active line in code (return, loop, or calculation)
        active_line = 2
        lines = code.split("\n")
        for idx, l in enumerate(lines, 1):
            s = l.strip()
            if s.startswith("return ") or "print(" in s or s.startswith("if ") or s.startswith("while "):
                active_line = idx
                break

        return {
            "summary": "One or more test cases did not match the expected output.",
            "error_hint": None,
            "logic_explanation": f"Logic issue: {diagnosis} Test case input: `{inp}`. Your code produced `{got}`, but the expected output was `{exp}`.",
            "failing_case": {
                "input": inp if not is_hidden else "(Hidden edge case: verify boundary constraints)",
                "expected": exp if not is_hidden else "(Hidden expected result)",
                "got": got
            },
            "complexity_tip": "Ensure your approach handles both the average case and minimum/maximum boundary constraints.",
            "hints": {
                "level_1": "Conceptual Invariant: Trace how the first and last elements in the sequence affect your calculated result.",
                "level_2": f"Simpler Clue: Look at Line {active_line}. Check whether your accumulator initialization (0 vs 1) or boundary comparison operator (< vs <=) skips or alters values.",
                "level_3": "Algorithmic Approach: 1. Read and parse all input tokens. 2. Handle empty/single element edge cases upfront. 3. Iterate through elements while updating state. 4. Print or return the final result."
            }
        }

    return {
        "summary": "Review the problem description and sample test cases.",
        "error_hint": None,
        "logic_explanation": None,
        "failing_case": None,
        "complexity_tip": None,
        "hints": {
            "level_1": "Re-read the input and output format specifications.",
            "level_2": "Simpler Clue: Check that your program reads all lines from standard input and prints the expected format.",
            "level_3": "Algorithmic Approach: Break down the problem into input parsing, data transformation, and formatted output."
        }
    }


async def generate_feedback(
    code: str,
    language: str,
    problem_spec: Dict[str, Any],
    test_results: Dict[str, Any],
    hint_level: int = 1
) -> Dict[str, Any]:
    """
    Calls free-tier Gemini API with dynamic model tiering (Pro for complex, Flash for standard),
    falling back across models and to rule-based analysis.
    Applies strict leak guards so no raw solutions are exposed.
    """
    feedback = None
    api_key = get_gemini_api_key()

    if api_key:
        # Determine optimal model based on problem complexity
        problem_text = f"{problem_spec.get('title', '')}\n{problem_spec.get('summary', '')}\n{' '.join(problem_spec.get('constraints', []))}"
        target_model = get_optimal_gemini_model(problem_text, problem_spec)

        candidate_models = PRO_FALLBACKS if target_model in PRO_FALLBACKS else FLASH_FALLBACKS
        # Ensure target_model is first, followed by others without duplicates
        ordered_models = [target_model] + [m for m in candidate_models if m != target_model]

        prompt_content = f"""
{FEEDBACK_SYSTEM_PROMPT}

PROBLEM SPEC:
Title: {problem_spec.get('title')}
Summary: {problem_spec.get('summary')}
Constraints: {problem_spec.get('constraints')}

LANGUAGE: {language}
USER CODE:
```
{code}
```

TEST RESULTS SUMMARY:
Overall status: {test_results.get('overall_status')}
Total tests: {test_results.get('total_tests')}
Passed count: {test_results.get('passed_count')}
Failed count: {test_results.get('failed_count')}
Timeout count: {test_results.get('timeout_count', 0)}
Error count: {test_results.get('error_count', 0)}
Test Details: {json.dumps(test_results.get('tests', [])[:3], indent=2)}

REQUESTED HINT LEVEL: {hint_level}
"""
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt_content}]}],
            "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"}
        }

        for model_name in ordered_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
            try:
                async with httpx.AsyncClient(timeout=25.0) as client:
                    resp = await client.post(url, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        candidates = data.get("candidates", [])
                        if candidates:
                            text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                            clean_text = re.sub(r"^```json\s*", "", text.strip())
                            clean_text = re.sub(r"\s*```$", "", clean_text.strip())
                            feedback = json.loads(clean_text)
                            if feedback:
                                feedback["model_used"] = model_name
                                break
                    elif resp.status_code in (429, 404, 503):
                        # Rate limited or model unavailable, try next fallback model
                        continue
            except Exception:
                continue

    if not feedback:
        feedback = _generate_rule_based_feedback(code, language, problem_spec, test_results, hint_level)
        feedback["model_used"] = "rule-based-engine"

    # Sanitize all hint fields with leak_guard
    if feedback.get("error_hint"):
        feedback["error_hint"] = leak_guard(feedback["error_hint"])
    if feedback.get("logic_explanation"):
        feedback["logic_explanation"] = leak_guard(feedback["logic_explanation"])

    hints = feedback.get("hints", {})
    for lvl in ("level_1", "level_2", "level_3"):
        if lvl in hints:
            hints[lvl] = leak_guard(hints[lvl])
    feedback["hints"] = hints

    # Attach the active hint corresponding to hint_level
    active_hint_key = f"level_{min(max(hint_level, 1), 3)}"
    feedback["active_hint"] = hints.get(active_hint_key, hints.get("level_1", ""))
    feedback["hint_level"] = hint_level

    return feedback
