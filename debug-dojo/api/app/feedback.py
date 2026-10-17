"""
AI Feedback Engine.
Provides case-by-case diagnosis, error hints, logic explanations,
time/space complexity tips, and progressive leak-guarded hint levels.
"""

import os
import re
import json
from typing import Dict, Any, Optional
import httpx

from .llm import leak_guard

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "") or os.environ.get("AI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")


FEEDBACK_SYSTEM_PROMPT = """You are an encouraging and pedagogically rigorous coding coach.
You help learners understand their mistakes WITHOUT giving away the complete solution code.
Analyze the user's submitted code, the problem specification, the test results, and the requested hint level.

Return a STRICT JSON object with this schema:
{
  "summary": "1-2 sentence overall assessment of the attempt",
  "error_hint": "If syntax/compile/runtime error: short hint about the line number and type of mistake. No full code fixes. Otherwise null.",
  "logic_explanation": "If wrong answer: explain WHERE the logic is wrong and why (e.g. loop boundary, empty input handling). Otherwise null.",
  "failing_case": {
    "input": "...",
    "expected": "...",
    "got": "..."
  },
  "complexity_tip": "If all tests pass: time and space complexity analysis (e.g. O(N) time, O(1) space) and optimization tips. Otherwise brief note on efficiency.",
  "hints": {
    "level_1": "A subtle conceptual nudge (e.g. check boundary condition or variable initialization)",
    "level_2": "A stronger hint pinpointing the logic discrepancy without giving code",
    "level_3": "A high-level algorithmic approach outline (e.g. step-by-step pseudo-concept)"
  }
}

RULES:
- Never provide full working code blocks.
- Keep hints conceptual and actionable.
- Output raw JSON only.
"""


def _generate_rule_based_feedback(
    code: str,
    language: str,
    problem_spec: Dict[str, Any],
    test_results: Dict[str, Any],
    hint_level: int = 1
) -> Dict[str, Any]:
    """Offline rule-based fallback when Gemini API is unconfigured."""
    all_passed = test_results.get("all_passed", False)
    tests = test_results.get("tests", [])
    
    first_failed = None
    first_error = None
    for t in tests:
        if t.get("status") in ("error", "timeout") and not first_error:
            first_error = t
        elif t.get("status") == "failed" and not first_failed:
            first_failed = t

    if all_passed:
        return {
            "summary": "Solved! All test cases passed successfully. Excellent work!",
            "error_hint": None,
            "logic_explanation": None,
            "failing_case": None,
            "complexity_tip": "Optimal Performance: Your solution achieves O(N) linear time complexity with O(1) auxiliary space.",
            "hints": {
                "level_1": "Great job! Try to see if you can solve it with fewer lines or zero extra memory allocations.",
                "level_2": "Consider in-place operations if dealing with arrays or strings.",
                "level_3": "Benchmark your solution on larger inputs (N = 10^5) to measure runtime bounds."
            }
        }

    if first_error:
        stderr = first_error.get("stderr") or first_error.get("compile_output") or "Runtime error"
        # Try to find line number
        line_match = re.search(r"line (\d+)", stderr, re.IGNORECASE)
        line_num = line_match.group(1) if line_match else "unknown"
        error_type = stderr.split("\n")[-1].strip() or "Exception"
        
        return {
            "summary": f"Your code encountered an error during execution ({first_error.get('status_desc', 'Error')}).",
            "error_hint": f"Mistake detected around line {line_num} ({error_type}). Verify syntax, proper type conversions, and boundary checks before indexing.",
            "logic_explanation": None,
            "failing_case": {
                "input": first_error.get("input", ""),
                "expected": first_error.get("expected", ""),
                "got": first_error.get("got", "") or "[Error: Process terminated]"
            },
            "complexity_tip": "Fix runtime exceptions first before analyzing asymptotic complexity.",
            "hints": {
                "level_1": f"Check line {line_num} for potential null/None values, invalid types, or out-of-range bounds.",
                "level_2": "Verify that all input tokens are converted to their expected types (e.g. integers or floats).",
                "level_3": "Add a conditional safeguard before accessing indices or performing mathematical operations."
            }
        }

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
                "level_1": "Carefully trace how your logic processes the first and last elements in the sequence.",
                "level_2": "Check if an initial accumulator value (like 0 vs 1) or an unhandled boundary case alters the final output.",
                "level_3": "Consider a structured pass: first parse all input tokens, then iterate while guarding against empty collections."
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
            "level_2": "Check that your program reads all lines from standard input.",
            "level_3": "Break down the problem into smaller helper functions."
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
    Calls Gemini AI to generate intelligent feedback, falling back to rule-based analysis.
    Applies strict leak guards so no raw solutions are exposed.
    """
    feedback = None

    if GEMINI_API_KEY:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
        
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
Test Details: {json.dumps(test_results.get('tests', [])[:3], indent=2)}

REQUESTED HINT LEVEL: {hint_level}
"""
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt_content}]}],
            "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"}
        }

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        clean_text = re.sub(r"^```json\s*", "", text.strip())
                        clean_text = re.sub(r"\s*```$", "", clean_text.strip())
                        feedback = json.loads(clean_text)
        except Exception:
            feedback = None

    if not feedback:
        feedback = _generate_rule_based_feedback(code, language, problem_spec, test_results, hint_level)

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
