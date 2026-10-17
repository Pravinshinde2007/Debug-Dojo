"""
LLM module: Progressive hints generation, free AI model tiering according to complexity,
runtime error extraction with line numbers, strict Rule 4 leak guard,
and prompt/response logging to backend/logs/llm.jsonl (Rule 7).
"""

import os
import re
from typing import Dict, Any, Optional, Tuple, List
from .db import log_llm_call

# Free-tier Gemini models
DEFAULT_FLASH_MODEL = os.environ.get("GEMINI_FLASH_MODEL", "gemini-2.5-flash")
DEFAULT_PRO_MODEL = os.environ.get("GEMINI_PRO_MODEL", "gemini-2.5-pro")

# Fallback models in case newer preview model IDs are unavailable
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


def get_gemini_api_key() -> str:
    """Retrieves Gemini/Google AI Studio API key from standard environment variables."""
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
        # Match Python tracebacks: File "...", line 12 or line 12
        line_matches = re.findall(r"line\s+(\d+)", clean_stderr, re.IGNORECASE)
        if line_matches:
            line_number = int(line_matches[-1])
    elif language.lower() in ("javascript", "node", "js"):
        # Match JS tracebacks: at ...:12:34 or solution.js:12
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

    # 2. Extract Error Type & Message
    error_lines = [l.strip() for l in clean_stderr.split("\n") if l.strip()]
    raw_error = error_lines[-1] if error_lines else "Exception"

    # Identify standard Python/Common exceptions
    error_type = "RuntimeError"
    if ":" in raw_error:
        error_type = raw_error.split(":")[0].strip()
    elif len(raw_error.split()) == 1:
        error_type = raw_error.strip()

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


def generate_hint(submission: Dict[str, Any], hint_index: int) -> str:
    """
    Rule 4 & Chronological Progressive Hints:
    - Hint 1: Broad conceptual invariant / high-level thinking nudge.
    - Hint 2: Simpler & distinctly different targeted clue directly pointing towards the fix.
    - Hint 3: High-level algorithmic recipe / step-by-step approach outline.
    - Hint 4: Edge case validation check.
    No hint may contain complete solutions or raw code.
    """
    hints = [
        # Hint 1: High-level conceptual invariant
        "Review the core invariant governing this problem: what mathematical relationship or structure connects the inputs to the output?",
        # Hint 2: Simpler, different, and directly pointing towards the fix
        "Simpler Clue: Check your primary loop and calculation line. Ensure that your accumulator begins at the proper initial value and that your comparison condition handles values exactly on the boundary.",
        # Hint 3: Algorithmic Approach Outline
        "Algorithmic Approach: 1. Parse all inputs from stdin. 2. Initialize your state/table. 3. Traverse elements once while updating results. 4. Return or print the final answer outside the loop.",
        # Hint 4: Edge case protection
        "Edge Case Check: Test what occurs when the input has 0 or 1 elements, negative numbers, or duplicates."
    ]
    idx = max(0, min(hint_index - 1, len(hints) - 1))
    hint_text = hints[idx]

    safe_hint = leak_guard(hint_text)

    # Rule 7: Log every prompt and response to backend/logs/llm.jsonl
    log_llm_call(
        prompt=f"Generate hint level {hint_index} for submission {submission.get('id', 'unknown')}",
        response=safe_hint,
        context=f"submission_id={submission.get('id', 'unknown')}, challenge_id={submission.get('challenge_id', 'unknown')}"
    )

    return safe_hint
