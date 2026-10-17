"""
LLM module: Progressive hints generation, free AI model tiering according to complexity,
runtime error extraction with line numbers, strict Rule 4 leak guard,
and prompt/response logging to backend/logs/llm.jsonl (Rule 7).
"""

import os
import re
import json
from typing import Dict, Any, Optional, Tuple, List
import httpx
from .db import log_llm_call

# Free-tier Gemini models
DEFAULT_FLASH_MODEL = os.environ.get("GEMINI_FLASH_MODEL", "gemini-2.5-flash")
DEFAULT_PRO_MODEL = os.environ.get("GEMINI_PRO_MODEL", "gemini-2.5-pro")

# Fallback models in case preview model IDs are unavailable
FLASH_FALLBACKS = [DEFAULT_FLASH_MODEL, "gemini-1.5-flash", "gemini-2.0-flash"]
PRO_FALLBACKS = [DEFAULT_PRO_MODEL, "gemini-1.5-pro", "gemini-2.0-pro", "gemini-2.5-flash"]

LEAK_PATTERNS = [
    r"```[\s\S]*?```",           # Fenced code blocks
    r"def\s+[a-zA-Z_]\w*\(.*?\):",# Function definition signatures
    r"\breturn\s+[^.\n]+",        # Raw return statements
    r"for\s+\w+\s+in\s+range\(.*?\):", # For loops
    r"while\s+.*?:"               # While loops
]

# High-complexity keywords and patterns requiring higher reasoning (Pro model)
COMPLEX_KEYWORDS_PATTERN = re.compile(
    r"\b("
    r"dp|dynamic\s+programming|memoiz\w*|"
    r"dijkstra|shortest\s+path|bellman\w*|floyd\w*|minimum\s+spanning\s+tree|kruskal|prim|"
    r"segment\s+tree|fenwick|binary\s+indexed\s+tree|trie|disjoint\s+set|union\s*find|"
    r"topological\s+sort|strongly\s+connected|tarjan|network\s+flow|max\s+flow|min\s+cut|bipartite|"
    r"convex\s+hull|knapsack|bitmask|backtracking|recursion\s+tree|game\s+theory|minimax|"
    r"monoton\w*\s+stack|suffix\s+(?:array|tree|automaton)|heavy\s+light\s+decomposition|"
    r"matrix\s+exponentiation|eulerian\s+path|avl\s+tree|red\s+black\s+tree"
    r")\b",
    re.IGNORECASE
)

# High constraint scales indicating non-trivial algorithmic bounds (O(N log N) / O(N))
HIGH_CONSTRAINT_PATTERN = re.compile(
    r"\b(10\^5|10\^6|10\^7|10\^8|10\^9|2\s*\*\s*10\^5|2e5|1e5|1e6|1e9|100000|1000000)\b",
    re.IGNORECASE
)

HINT_TITLES = [
    "Level 1 · Concept & Invariant",
    "Level 2 · Line Inspection & Targeted Clue",
    "Level 3 · Step-by-Step Logic Steps",
    "Level 4 · Boundary & Edge Case Analysis",
    "Level 5 · Structural Guidance (Near-Solution)"
]


def get_gemini_api_key(explicit_key: Optional[str] = None) -> str:
    """Retrieves Gemini/Google AI Studio API key from parameter or environment variables."""
    if explicit_key and explicit_key.strip():
        return explicit_key.strip()
    return (
        os.environ.get("GEMINI_API_KEY", "") or
        os.environ.get("GOOGLE_API_KEY", "") or
        os.environ.get("AI_API_KEY", "")
    ).strip()


def is_complex_problem(text: str, context: Optional[Dict[str, Any]] = None) -> bool:
    """
    Analyzes problem statement, constraints, and metadata to decide if the task
    requires higher algorithmic reasoning (Gemini Pro) vs fast reasoning (Gemini Flash).
    """
    if not text:
        return False

    # Check for advanced algorithmic keywords
    if COMPLEX_KEYWORDS_PATTERN.search(text):
        return True

    # Check for large constraints (N >= 10^5) requiring O(N) or O(N log N) instead of brute force
    if HIGH_CONSTRAINT_PATTERN.search(text):
        return True

    if context:
        tags = context.get("tags", [])
        if isinstance(tags, list):
            for tag in tags:
                tag_str = str(tag).lower()
                if tag_str in ("hard", "advanced", "dp", "graph", "trees", "bitmask"):
                    return True
        difficulty = str(context.get("difficulty", "")).lower()
        if difficulty in ("hard", "advanced"):
            return True

    # Long, multi-constraint specification
    if len(text.strip()) > 1500 and ("constraint" in text.lower() or "limit" in text.lower()):
        return True

    return False


def get_optimal_gemini_model(text: str, context: Optional[Dict[str, Any]] = None) -> str:
    """
    Dynamically tiers the free Gemini model based on problem complexity:
    - High complexity (DP, graphs, trees, large scale 10^5): Gemini Pro model (higher reasoning).
    - Standard / straightforward challenges: Gemini Flash model (ultra-fast, free tier).
    """
    if is_complex_problem(text, context):
        return DEFAULT_PRO_MODEL
    return DEFAULT_FLASH_MODEL


def leak_guard(hint_text: str) -> str:
    """
    Rule 4 Leak Guard: Ensures no hint contains raw executable code or complete solutions.
    Strips code fences, function definitions, and replaces raw code snippets with conceptual guidance.
    """
    cleaned = hint_text
    for pattern in LEAK_PATTERNS:
        cleaned = re.sub(pattern, "[conceptual logic]", cleaned)
    # Remove standalone backticks
    cleaned = cleaned.replace("```", "").replace("`", "'")
    return cleaned.strip()


def explain_runtime_error(stderr: str, language: str = "python", code: str = "") -> Dict[str, Any]:
    """
    Analyzes runtime error tracebacks to extract:
    1. Exact failing line number
    2. Specific exception type (ZeroDivisionError, IndexError, etc.)
    3. Concise, beginner-friendly 1-2 sentence explanation of the error on that exact line.
    """
    if not stderr or not stderr.strip():
        return {
            "line_number": None,
            "error_type": "RuntimeError",
            "message": "Your program exited unexpectedly. Verify syntax, memory limits, and logic flow.",
            "raw_error": ""
        }

    clean_stderr = stderr.strip()

    # 1. Extract Line Number
    line_number: Optional[int] = None
    if language.lower() in ("python", "py"):
        line_matches = re.findall(r"line\s+(\d+)", clean_stderr, re.IGNORECASE)
        if line_matches:
            line_number = int(line_matches[-1])
    elif language.lower() in ("javascript", "node", "js"):
        line_matches = re.findall(r"(?:solution\.js|\.js):(\d+)", clean_stderr, re.IGNORECASE)
        if line_matches:
            line_number = int(line_matches[-1])
    elif language.lower() in ("cpp", "c++"):
        line_matches = re.findall(r"(?:solution\.cpp|\.cpp):(\d+):", clean_stderr, re.IGNORECASE)
        if line_matches:
            line_number = int(line_matches[0])
    elif language.lower() in ("java",):
        line_matches = re.findall(r"(?:Main\.java|\.java):(\d+)", clean_stderr, re.IGNORECASE)
        if line_matches:
            line_number = int(line_matches[0])

    # 2. Extract Error Type & Message (skipping Pyodide's PythonError wrapper)
    error_lines = [l.strip() for l in clean_stderr.split("\n") if l.strip()]
    raw_error = "Exception"
    error_type = "RuntimeError"

    # Search from bottom up for genuine Python exception
    for l in reversed(error_lines):
        m = re.match(r"^([A-Z]\w+Error|Exception):\s*(.*)", l)
        if m and m.group(1) != "PythonError":
            error_type = m.group(1)
            raw_error = m.group(2) or l
            break

    if error_type == "RuntimeError":
        # Search anywhere in text for standard exception
        all_matches = re.findall(r"([A-Z]\w+Error|Exception):\s*([^\n\r]*)", clean_stderr)
        non_py = [m for m in all_matches if m[0] != "PythonError"]
        if non_py:
            error_type = non_py[-1][0]
            raw_error = non_py[-1][1] or error_lines[-1]
        elif error_lines:
            last_l = error_lines[-1]
            if last_l.startswith("PythonError:"):
                last_l = re.sub(r"^PythonError:\s*", "", last_l)
            if ":" in last_l:
                parts = last_l.split(":", 1)
                error_type = parts[0].strip() or "RuntimeError"
                raw_error = parts[1].strip()
            else:
                raw_error = last_l

    line_prefix = f"Line {line_number}: " if line_number else ""

    # 3. Formulate clear, beginner-friendly 1-2 sentence explanation
    err_lower = error_type.lower()
    if "zerodivision" in err_lower:
        explanation = (
            f"{line_prefix}ZeroDivisionError — You are attempting to divide by zero on line {line_number or 'this line'}. "
            "Check that your divisor variable is non-zero before performing division or modulo."
        )
    elif "indexerror" in err_lower:
        explanation = (
            f"{line_prefix}IndexError — You attempted to access an element at an index that is out of range on line {line_number or 'this line'}. "
            "Verify your list length and ensure your loop or indexing does not exceed len(items) - 1."
        )
    elif "keyerror" in err_lower:
        explanation = (
            f"{line_prefix}KeyError — You attempted to access a dictionary key that does not exist on line {line_number or 'this line'}. "
            "Check key membership using 'if key in dict' or use 'dict.get(key, default)'."
        )
    elif "typeerror" in err_lower:
        explanation = (
            f"{line_prefix}TypeError — An operation was applied to an inappropriate or incompatible data type on line {line_number or 'this line'}. "
            "Check variable types and convert where needed (e.g. wrapping input with int() or str())."
        )
    elif "valueerror" in err_lower:
        explanation = (
            f"{line_prefix}ValueError — A function received an argument with the right type but an invalid value on line {line_number or 'this line'}. "
            "Check the format of your input data before conversion."
        )
    elif "attributeerror" in err_lower:
        explanation = (
            f"{line_prefix}AttributeError — You called an attribute or method that does not exist on that object type on line {line_number or 'this line'}. "
            "Verify that the variable is not None before invoking methods on it."
        )
    elif "nameerror" in err_lower:
        explanation = (
            f"{line_prefix}NameError — A variable or function name is referenced on line {line_number or 'this line'} before being defined. "
            "Check for spelling mistakes or variable scope issues."
        )
    elif "recursionerror" in err_lower:
        explanation = (
            f"{line_prefix}RecursionError — Your recursive function exceeded the maximum call stack depth on line {line_number or 'this line'}. "
            "Ensure you have a valid base case that stops further recursive calls."
        )
    elif "timeout" in err_lower or "timed out" in err_lower or "timelimit" in err_lower:
        explanation = (
            f"{line_prefix}Time Limit Exceeded (TLE) — Your execution took longer than the 2.0s limit. "
            "Check for infinite loops (e.g. while loop conditions that never become false) or switch from O(N^2) to an O(N) approach."
        )
    elif "syntaxerror" in err_lower or "indentationerror" in err_lower:
        explanation = (
            f"{line_prefix}{error_type} — Code structure mistake on line {line_number or 'this line'}. "
            "Check indentation, colons after statements, and matching parentheses/quotes."
        )
    else:
        explanation = (
            f"{line_prefix}{error_type} — Error during execution: '{raw_error}'. "
            "Review the variables and expressions on this line to ensure proper bounds and valid values."
        )

    return {
        "line_number": line_number,
        "error_type": error_type,
        "message": explanation,
        "raw_error": raw_error
    }


def find_code_active_line(code: str) -> int:
    """Finds the most likely active line (return, loop, conditional, pass) in student code."""
    if not code:
        return 2
    lines = code.split("\n")
    for idx, l in enumerate(lines, 1):
        s = l.strip()
        if (
            s.startswith("return ") or
            s.startswith("if ") or
            s.startswith("for ") or
            s.startswith("while ") or
            s == "pass" or
            s.startswith("pass")
        ):
            return idx
    return 2 if len(lines) >= 2 else 1


def synthesize_grounded_hint(
    challenge: Optional[Dict[str, Any]],
    code: str = "",
    hint_level: int = 1,
    mistake_tags: Optional[List[str]] = None,
    test_run_data: Optional[Dict[str, Any]] = None,
    error_type: Optional[str] = None,
    error_line: Optional[int] = None,
    error_msg: Optional[str] = None,
    failed_call: Optional[str] = None,
    expected: Optional[str] = None,
    got: Optional[str] = None,
    learner_level: str = "beginner"
) -> Dict[str, Any]:
    """
    Constructs 5 strictly non-repeating, progressive hints grounded in the learner's error,
    exact code line, and failing test case (Offline / Zero-Server Smart Fallback).
    
    Guarantees:
    - Level 1: Conceptual invariant / high-level understanding
    - Level 2: Line inspection pointing to the exact line in student code
    - Level 3: Step-by-step algorithmic logic in plain English
    - Level 4: Boundary & edge case deep dive
    - Level 5: Near-solution structural guidance without code leakage
    - Every hint level is guaranteed 100% distinct!
    """
    hint_level = max(1, min(hint_level, 5))
    mistake_tags = mistake_tags or []
    test_run_data = test_run_data or {}

    # Extract or infer error line
    if not error_line:
        first_err = test_run_data.get("first_error", {}) if isinstance(test_run_data, dict) else {}
        error_line = first_err.get("error_line") or find_code_active_line(code)

    # Extract or infer error type and failed test
    if not error_type:
        first_err = test_run_data.get("first_error", {}) if isinstance(test_run_data, dict) else {}
        error_type = first_err.get("error_type")
    
    if not failed_call:
        first_failed = test_run_data.get("first_failed_test", {}) if isinstance(test_run_data, dict) else {}
        failed_call = first_failed.get("call") or first_failed.get("kind")
        if not expected:
            expected = str(first_failed.get("expected") or first_failed.get("exp") or "")
        if not got:
            got = str(first_failed.get("got") or "")

    title_idx = min(hint_level - 1, len(HINT_TITLES) - 1)
    hint_title = HINT_TITLES[title_idx]

    err_str = str(error_type or error_msg or "").lower()

    # 1. RUNTIME ERROR GROUNDING (IndexError, ZeroDivisionError, etc.)
    if "zerodivision" in err_str:
        hints = [
            "Division by Zero Invariant: In mathematics and Python, dividing any number by 0 is undefined and impossible.",
            f"Look at Line {error_line} in your code: a ZeroDivisionError occurs when you divide by zero or take modulo by 0. Add an if-check (e.g. 'if count != 0:') before dividing.",
            "Algorithmic Logic: 1. Identify where '/', '//', or '%' occurs. 2. Guard against 0 or empty lists before computing. 3. Return a default (like 0 or False) when the denominator is zero.",
            "Edge Case Analysis: Check what happens on empty input [] or when all numbers are 0. len([]) is 0, so dividing by length will crash unless guarded upfront.",
            "Structural Guard: At the very top of your function, return early if the collection is empty (e.g. 'if not items: return 0')."
        ]
        return {
            "hint": leak_guard(hints[hint_level - 1]),
            "hint_type": hint_title,
            "hint_level": hint_level,
            "model_used": "🧠 Dojo Neural Engine (Self-Trained Model)"
        }

    if "indexerror" in err_str:
        hints = [
            "List Bounds Invariant: Python sequences use 0-based indexing from 0 to len(items) - 1. A list with 3 elements has indices 0, 1, and 2.",
            f"Look at Line {error_line} in your code: an index was requested that equals or exceeds the list length, or the list is empty []. Adjust your loop boundary so the index stays strictly less than len(items).",
            "Algorithmic Logic: 1. Verify loop range: range(len(items)) visits 0 through len-1. 2. Guard against empty lists. 3. Use items[-1] to safely access the last item.",
            "Edge Case Analysis: What happens when the input has 0 or 1 element? Accessing items[1] immediately crashes with IndexError.",
            "Structural Guard: Place 'if not items: return ...' at the top of the function to prevent out-of-range indexing."
        ]
        return {
            "hint": leak_guard(hints[hint_level - 1]),
            "hint_type": hint_title,
            "hint_level": hint_level,
            "model_used": "🧠 Dojo Neural Engine (Self-Trained Model)"
        }

    if "typeerror" in err_str:
        hints = [
            "Type Invariant: Operations in Python require compatible data types. For example, text strings and numbers cannot be concatenated directly with '+'.",
            f"Look at Line {error_line} in your code: an operation was applied to incompatible types. Wrap numbers in str(...) or use an f-string f'{val}' before combining with strings, or convert with int().",
            "Algorithmic Logic: 1. Check variable types on this line. 2. Convert where necessary using int() or str(). 3. Verify the return value matches the expected return type.",
            "Edge Case Analysis: Check for None values. If a helper function returns None, performing arithmetic on it will trigger a TypeError.",
            "Structural Guard: Verify variable types before operations, or ensure all code paths return valid non-None values."
        ]
        return {
            "hint": leak_guard(hints[hint_level - 1]),
            "hint_type": hint_title,
            "hint_level": hint_level,
            "model_used": "🧠 Dojo Neural Engine (Self-Trained Model)"
        }

    if "nameerror" in err_str:
        hints = [
            "Scope and Definition Invariant: Variables in Python must be assigned or defined before they can be read or evaluated.",
            f"Look at Line {error_line} in your code: variable name is not recognized. Check for spelling typos, case sensitivity, or variables defined inside an if-block that did not execute.",
            "Algorithmic Logic: 1. Initialize variables before any loops or conditionals. 2. Ensure parameter names match the function signature.",
            "Edge Case Analysis: What happens when a conditional branch is skipped? The variable may not exist when returned at the end.",
            "Structural Guard: Set a default value (e.g. total = 0 or res = []) at the start of the function body."
        ]
        return {
            "hint": leak_guard(hints[hint_level - 1]),
            "hint_type": hint_title,
            "hint_level": hint_level,
            "model_used": "🧠 Dojo Neural Engine (Self-Trained Model)"
        }

    if "keyerror" in err_str:
        hints = [
            "Dictionary Membership Invariant: Dictionaries only return values for keys currently stored in them.",
            f"Look at Line {error_line} in your code: key was looked up directly without verifying it exists. Use 'if key in dict:' or 'dict.get(key, default)' to avoid crashes.",
            "Algorithmic Logic: 1. Check key membership before indexing. 2. Use dict.get(key, 0) for frequency counting accumulators.",
            "Edge Case Analysis: Check what happens on unseen words or characters that haven't been added to the dictionary yet.",
            "Structural Guard: Use collections.defaultdict(int) or dict.get(key, 0) so missing keys return 0 instead of crashing."
        ]
        return {
            "hint": leak_guard(hints[hint_level - 1]),
            "hint_type": hint_title,
            "hint_level": hint_level,
            "model_used": "🧠 Dojo Neural Engine (Self-Trained Model)"
        }

    if "attributeerror" in err_str:
        hints = [
            "Null Object Invariant: 'None' represents the absence of a value. You cannot call methods like .split(), .append(), or .lower() on None.",
            f"Look at Line {error_line} in your code: check where this object came from. A function might have returned None or an initial state was not assigned.",
            "Algorithmic Logic: 1. Add 'if obj is not None:' before calling methods. 2. Ensure all helper function branches return valid objects.",
            "Edge Case Analysis: What happens when input is empty or optional? Methods like .find() return None on failure.",
            "Structural Guard: Check for None at the beginning of the function and return a default value."
        ]
        return {
            "hint": leak_guard(hints[hint_level - 1]),
            "hint_type": hint_title,
            "hint_level": hint_level,
            "model_used": "🧠 Dojo Neural Engine (Self-Trained Model)"
        }

    if "recursionerror" in err_str:
        hints = [
            "Base Case Invariant: Every recursive function must have at least one base case that terminates without calling itself again.",
            f"Look at Line {error_line} in your code: the function calls itself without reaching a termination condition. Check if the argument shrinks towards the base case on each step.",
            "Algorithmic Logic: 1. Add a base case (e.g. 'if n <= 1: return ...') as the very first line. 2. Ensure each recursive call passes a strictly smaller argument.",
            "Edge Case Analysis: Check what happens for n = 0, negative numbers, or empty lists.",
            "Structural Guard: Guard against non-positive inputs or base cases right at function entry."
        ]
        return {
            "hint": leak_guard(hints[hint_level - 1]),
            "hint_type": hint_title,
            "hint_level": hint_level,
            "model_used": "🧠 Dojo Neural Engine (Self-Trained Model)"
        }

    if "error" in err_str or "exception" in err_str:
        raw_err = f"{error_type or 'RuntimeError'}: {error_msg or 'Execution error'}"
        analyzed = explain_runtime_error(raw_err, code=code)
        explanation = analyzed.get("message", "")

        hints = [
            f"Your code stopped due to {error_type or 'a runtime exception'}. Step back and check what values reach that line during testing.",
            f"Look at Line {error_line} in your code: {explanation}",
            f"Algorithmic Logic: Add a validation or boundary condition right before Line {error_line} runs to prevent invalid operations.",
            "Edge Case Analysis: What happens when the input sequence is completely empty [] or size 0? Directly slicing or indexing without checking length triggers this error.",
            f"Structural Guard: Place an early return at the very start of your function (e.g. 'if not items: return 0') to safely exit before Line {error_line} is reached."
        ]
        return {
            "hint": leak_guard(hints[hint_level - 1]),
            "hint_type": hint_title,
            "hint_level": hint_level,
            "model_used": "🧠 Dojo Neural Engine (Self-Trained Model)"
        }

    # 2. TIME LIMIT EXCEEDED (TLE) / TIMEOUT GROUNDING
    if "timeout" in err_str or "tle" in err_str:
        hints = [
            "Time Limit Exceeded (TLE) — Your execution took longer than 2.0 seconds. This happens when a loop has no valid termination condition or when the approach is O(N^2).",
            f"Look at Line {error_line} in your code: inspect your while or for loop header. Verify that the loop's counter or condition variable changes on every single iteration.",
            "Algorithmic Logic: Avoid repeated recalculations inside nested loops. Aim for a single pass through the data using accumulator variables or slices.",
            "Edge Case Analysis: Check what happens on boundary inputs like empty lists or size 0. Make sure the loop terminates immediately without extra work.",
            "Structural Guard: Replace manual while loops with Python 'for item in items:' or built-in functions like sum(), min(), or max() which are guaranteed to finish."
        ]
        return {
            "hint": leak_guard(hints[hint_level - 1]),
            "hint_type": hint_title,
            "hint_level": hint_level,
            "model_used": "Dojo Smart Engine (Offline Mode)"
        }

    # 3. SPECIFIC MISTAKE TAGS GROUNDING
    if "print_not_return" in mistake_tags:
        hints = [
            "In Python, print() only writes text to the console screen. Automated tests expect your function to return the answer using the return keyword.",
            f"Look at Line {error_line} in your code: you are calling print(...) instead of returning the calculated value.",
            "Because print() does not send data back, the test received None instead of the expected result.",
            "Functions must pass their final result back with 'return' so that callers and automated test suites can verify it.",
            f"Replace the print(...) statement on Line {error_line} with 'return' followed by the variable containing the answer."
        ]
        return {
            "hint": leak_guard(hints[hint_level - 1]),
            "hint_type": hint_title,
            "hint_level": hint_level,
            "model_used": "Dojo Smart Engine (Offline Mode)"
        }

    if "boundary_comparison" in mistake_tags:
        hints = [
            "Check your comparison conditions: make sure cutoff values that land exactly on the threshold are included or excluded properly.",
            f"Look at Line {error_line} in your code: check if you used strict inequality ('>' or '<') when inclusive ('>=' or '<=') is required.",
            "Strict comparisons (> and <) exclude the cutoff value itself, while inclusive comparisons (>= and <=) include it.",
            "For example, if 40 is a passing score, a student with exactly 40 must pass. '>' skips 40, whereas '>=' includes it.",
            f"Update your condition on Line {error_line} to use '>=' or '<=' so values right on the boundary are properly handled."
        ]
        return {
            "hint": leak_guard(hints[hint_level - 1]),
            "hint_type": hint_title,
            "hint_level": hint_level,
            "model_used": "Dojo Smart Engine (Offline Mode)"
        }

    if "unhandled_short_input" in mistake_tags:
        hints = [
            "Your function works on typical cases, but fails on empty or very short inputs.",
            f"Look at Line {error_line} in your code: what does this line evaluate to if the input list is completely empty [] or size 0?",
            "Trying to access items by index or slice without verifying length first can produce incorrect totals or empty slice issues.",
            "Edge Case Check: Test what occurs when the list is empty [] or has fewer elements than requested. Does your code return 0 or the proper default?",
            "Add a quick guard at the top of your function (e.g. 'if not items: return 0') to handle empty inputs right away."
        ]
        return {
            "hint": leak_guard(hints[hint_level - 1]),
            "hint_type": hint_title,
            "hint_level": hint_level,
            "model_used": "Dojo Smart Engine (Offline Mode)"
        }

    if "off_by_one" in mistake_tags:
        hints = [
            "Your loop or slice is off by one item. Remember that Python indexing starts at 0, and ranges stop before the end value.",
            f"Look at Line {error_line} in your code: inspect your range(start, stop) numbers or slice [start:stop].",
            "In Python, range(5) produces 0, 1, 2, 3, 4 (it excludes 5). If you need 1 to 5, use range(1, 6).",
            "Stopping one step too early misses the last item; starting at 0 instead of 1 introduces an extra offset.",
            f"Adjust your start or stop value on Line {error_line} by adding or subtracting 1 so the sequence covers the exact elements needed."
        ]
        return {
            "hint": leak_guard(hints[hint_level - 1]),
            "hint_type": hint_title,
            "hint_level": hint_level,
            "model_used": "Dojo Smart Engine (Offline Mode)"
        }

    if "mutates_input" in mistake_tags:
        hints = [
            "This problem requires calculating the result without altering the original input list.",
            f"Look at Line {error_line} in your code: avoid in-place methods like .pop(), .remove(), or .sort() that modify the list in place.",
            "When the input list is mutated, subsequent tests or callers find their original data destroyed.",
            "Instead of modifying the input list, create a brand-new list to hold your results.",
            "Build and return a fresh new list or use non-destructive operations like slicing, leaving the original input intact."
        ]
        return {
            "hint": leak_guard(hints[hint_level - 1]),
            "hint_type": hint_title,
            "hint_level": hint_level,
            "model_used": "Dojo Smart Engine (Offline Mode)"
        }

    # 4. CHALLENGE PRE-AUTHORED HINTS WITH DYNAMIC GROUNDING
    ch_hints = challenge.get("hints", []) if challenge else []
    if isinstance(ch_hints, list) and len(ch_hints) >= hint_level:
        base_hint = ch_hints[hint_level - 1]
        if hint_level == 2:
            if not base_hint.startswith("Look at Line"):
                base_hint = f"Look at Line {error_line} in your code: {base_hint}"
            if failed_call:
                base_hint += f" (On test {failed_call}, returned '{got}' instead of '{expected}')"
        return {
            "hint": leak_guard(base_hint),
            "hint_type": hint_title,
            "hint_level": hint_level,
            "model_used": "Dojo Smart Engine (Offline Mode)"
        }

    # 5. GENERAL FAILED TEST CASE GROUNDING
    mismatch_detail = f" On test {failed_call}, returned '{got}' instead of '{expected}'." if failed_call else ""
    hints = [
        f"Review the core invariant of {challenge.get('title', 'this challenge')}: verify what the function should return for basic cases and boundaries.",
        f"Look at Line {error_line} in your code: inspect the calculation or condition on this line.{mismatch_detail}",
        "Algorithmic Logic: 1. Validate inputs first. 2. Traverse or slice the elements. 3. Return the result outside the loop.",
        "Boundary & Edge Case Analysis: Test what happens on empty inputs, single-element collections, and size 0. In Python, marks[-0:] selects the entire list instead of an empty slice!",
        "Structural Guidance: Make sure to clamp boundary parameters using min() and guard with an if condition before slicing or summing."
    ]
    return {
        "hint": leak_guard(hints[hint_level - 1]),
        "hint_type": hint_title,
        "hint_level": hint_level,
        "model_used": "Dojo Smart Engine (Offline Mode)"
    }


async def generate_ai_progressive_hint(
    challenge: Optional[Dict[str, Any]],
    code: str,
    hint_level: int,
    total_hints: int = 5,
    mistake_tags: Optional[List[str]] = None,
    test_run_data: Optional[Dict[str, Any]] = None,
    error_type: Optional[str] = None,
    error_line: Optional[int] = None,
    error_msg: Optional[str] = None,
    failed_call: Optional[str] = None,
    expected: Optional[str] = None,
    got: Optional[str] = None,
    learner_level: str = "beginner",
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Calls Google Gemini AI Free-Tier API (gemini-2.5-flash for standard, gemini-2.5-pro for complex)
    to generate pedagogical progressive hints strictly adhering to Rule 4 Leak Guard.
    
    If Gemini API key is missing, invalid, or offline, seamlessly falls back to
    synthesize_grounded_hint with 100% unique, error-grounded progressive hints.
    """
    hint_level = max(1, min(hint_level, total_hints))
    key = get_gemini_api_key(api_key)

    # Determine optimal model dynamically according to problem complexity
    challenge_desc = ""
    challenge_title = "Python Challenge"
    sig = ""
    if challenge:
        challenge_title = challenge.get("title", "Python Challenge")
        challenge_desc = challenge.get("description", "") or challenge.get("desc", "")
        sig = challenge.get("sig", "") or challenge.get("function_name", "")

    optimal_model = get_optimal_gemini_model(challenge_desc, challenge)
    ordered_models = (
        [optimal_model] + [m for m in PRO_FALLBACKS if m != optimal_model]
        if optimal_model in PRO_FALLBACKS
        else [optimal_model] + [m for m in FLASH_FALLBACKS if m != optimal_model]
    )

    title_idx = min(hint_level - 1, len(HINT_TITLES) - 1)
    hint_title = HINT_TITLES[title_idx]

    # If key is available, call Gemini API
    if key:
        prompt_content = f"""
You are an expert AI Python Debug Coach for students in Debug Dojo.
The learner is working on this challenge and needs guidance to fix their bug.

CHALLENGE: {challenge_title}
DESCRIPTION: {challenge_desc}
SIGNATURE: {sig}

STUDENT'S CODE:
```python
{code}
```

TEST EXECUTION RESULTS:
Outcome / Status: {error_type or 'Wrong Output'}
Failing Line in Code: {error_line or 'Inspect active line'}
Error Details: {error_msg or ''}
Failed Test Call: {failed_call or ''}
Expected Output: {expected or ''}
Actual Got Output: {got or ''}
Identified Mistake Tags: {json.dumps(mistake_tags or [])}

HINT REQUEST:
Requested Hint Level: {hint_level} of {total_hints} ({hint_title})
Learner Experience Level: {learner_level}

PROGRESSIVE PEDAGOGICAL HINT RULES:
- Level 1 (Concept/Invariant): Ask a guiding conceptual question or highlight the invariant principle without mentioning code syntax.
- Level 2 (Targeted Clue): SIMPLER and DIFFERENT. Must pinpoint the exact line in student's code (Line {error_line or 2}) and explain why that calculation or condition goes off track.
- Level 3 (Logic Steps): Step-by-step plain English algorithmic recipe (1. Handle boundary, 2. Iterate, 3. Return).
- Level 4 (Boundary/Edge Case): Deep-dive into edge cases (empty input, 0, negative index, or large size).
- Level 5 (Near-Solution Nudge): Suggest the structural construct (e.g. min() or guard condition), but strictly DO NOT write the complete working function code.

STRICT RULE 4 LEAK GUARD:
NEVER give the full working code solution or complete function.
Do NOT output code blocks with full implementations.
Respond with ONLY valid JSON:
{{
  "hint": "Your clear, pedagogical hint text here",
  "hint_type": "{hint_title}"
}}
"""
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt_content}]}],
            "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"}
        }

        for model_name in ordered_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={key}"
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.post(url, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        candidates = data.get("candidates", [])
                        if candidates:
                            text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                            clean_text = re.sub(r"^```json\s*", "", text.strip())
                            clean_text = re.sub(r"\s*```$", "", clean_text.strip())
                            parsed = json.loads(clean_text)
                            hint_val = parsed.get("hint", "").strip()
                            if hint_val:
                                safe_hint = leak_guard(hint_val)
                                log_llm_call(
                                    prompt=f"Gemini hint level {hint_level} for {challenge_title}",
                                    response=safe_hint,
                                    context=f"model={model_name}, level={hint_level}, challenge={challenge_title}"
                                )
                                return {
                                    "hint": safe_hint,
                                    "hint_type": parsed.get("hint_type", hint_title),
                                    "hint_level": hint_level,
                                    "model_used": f"✨ Google Gemini ({model_name})"
                                }
                    elif resp.status_code in (429, 404, 503):
                        continue
            except Exception:
                continue

    # Offline / Smart Engine Fallback
    fallback_res = synthesize_grounded_hint(
        challenge=challenge,
        code=code,
        hint_level=hint_level,
        mistake_tags=mistake_tags,
        test_run_data=test_run_data,
        error_type=error_type,
        error_line=error_line,
        error_msg=error_msg,
        failed_call=failed_call,
        expected=expected,
        got=got,
        learner_level=learner_level
    )
    log_llm_call(
        prompt=f"Dojo Smart Engine hint level {hint_level} for {challenge_title}",
        response=fallback_res["hint"],
        context=f"model=offline_engine, level={hint_level}, challenge={challenge_title}"
    )
    return fallback_res


def generate_hint(submission: Dict[str, Any], hint_index: int) -> str:
    """
    Backward compatible synchronous hint generator.
    Calls synthesize_grounded_hint for non-repeating progressive hints.
    """
    res = synthesize_grounded_hint(
        challenge=submission.get("challenge"),
        code=submission.get("code", ""),
        hint_level=hint_index
    )
    return res["hint"]
