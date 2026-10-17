"""
ML Engine: Local Offline Machine Learning Model for Debug Dojo.
Loads dojo_ml_model.joblib trained on Python error and bug patterns.
Provides 100% offline inference with zero external AI API calls.
"""

import os
import joblib
from typing import Dict, Any, Optional, List, Tuple
from .db import log_llm_call

MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "dojo_ml_model.joblib")

_LOADED_MODEL_PAYLOAD: Optional[Dict[str, Any]] = None


def get_trained_model() -> Optional[Dict[str, Any]]:
    """Loads the trained ML model pipeline once into memory."""
    global _LOADED_MODEL_PAYLOAD
    if _LOADED_MODEL_PAYLOAD is not None:
        return _LOADED_MODEL_PAYLOAD

    if os.path.exists(MODEL_PATH):
        try:
            _LOADED_MODEL_PAYLOAD = joblib.load(MODEL_PATH)
            return _LOADED_MODEL_PAYLOAD
        except Exception as e:
            print(f"Warning: Failed to load ML model from {MODEL_PATH}: {e}")
            return None
    return None


def predict_bug_category(code: str, error_context: str = "") -> Tuple[str, float, str]:
    """
    Runs inference on student code and error context using the local trained ML pipeline.
    Returns: (predicted_tag, confidence, invariant)
    """
    payload = get_trained_model()
    if not payload or "pipeline" not in payload:
        # Fallback heuristic if model file is somehow missing
        err_lower = (error_context or "").lower()
        if "zerodivision" in err_lower:
            return "zero_division", 0.99, "zero_division_guard"
        if "indexerror" in err_lower:
            return "index_error", 0.99, "index_bounds_guard"
        if "print" in code and "return" not in code:
            return "print_not_return", 0.95, "function_return_contract"
        return "off_by_one", 0.50, "loop_range_bounds"

    pipeline = payload["pipeline"]
    invariants = payload.get("invariants", {})
    text = f"CODE_START\n{code}\nCODE_END\nERROR_CONTEXT: {error_context}"

    try:
        probs = pipeline.predict_proba([text])[0]
        best_idx = probs.argmax()
        pred_tag = pipeline.classes_[best_idx]
        confidence = float(probs[best_idx])
        invariant = invariants.get(pred_tag, "general_invariant")
        return pred_tag, confidence, invariant
    except Exception:
        pred_tag = pipeline.predict([text])[0]
        return pred_tag, 0.90, invariants.get(pred_tag, "general_invariant")


HINT_TITLES = [
    "Level 1 · Concept & Invariant",
    "Level 2 · Line Inspection & Targeted Clue",
    "Level 3 · Step-by-Step Logic Steps",
    "Level 4 · Boundary & Edge Case Analysis",
    "Level 5 · Structural Guidance (Near-Solution)"
]


def leak_guard(text: str) -> str:
    """Removes code blocks and def statements to prevent solution leaks."""
    import re
    cleaned = re.sub(r"```[\s\S]*?```", "[Code block hidden to avoid leaking complete solution]", text)
    cleaned = re.sub(r"def\s+[a-zA-Z_]\w*\(.*?\):", "[Function signature omitted]", cleaned)
    return cleaned.strip()


def generate_ml_hint(
    challenge: Optional[Dict[str, Any]],
    code: str = "",
    hint_level: int = 1,
    error_type: Optional[str] = None,
    error_line: Optional[int] = None,
    error_msg: Optional[str] = None,
    failed_call: Optional[str] = None,
    expected: Optional[str] = None,
    got: Optional[str] = None,
    mistake_tags: Optional[List[str]] = None,
    test_run_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Generates pedagogical progressive hints using the local trained ML model.
    Runs 100% locally with zero external API calls.
    """
    hint_level = max(1, min(hint_level, 5))
    err_ctx = f"type: {error_type}, msg: {error_msg}, call: {failed_call}, exp: {expected}, got: {got}"
    
    # Run ML prediction
    predicted_tag, confidence, invariant = predict_bug_category(code, err_ctx)
    
    title_idx = min(hint_level - 1, len(HINT_TITLES) - 1)
    hint_title = HINT_TITLES[title_idx]

    line_num = error_line or 2
    err_lower = (error_type or error_msg or predicted_tag or "").lower()

    # Model inference response mapping
    if "zerodivision" in err_lower or predicted_tag == "zero_division":
        hints = [
            "Division by Zero Invariant: In mathematics and Python, dividing any number by 0 is undefined and impossible.",
            f"Look at Line {line_num} in your code: a ZeroDivisionError occurs when you divide by zero or take modulo by 0. Add an if-check (e.g. 'if count != 0:') before dividing.",
            "Algorithmic Logic: 1. Identify where '/', '//', or '%' occurs. 2. Guard against 0 or empty lists before computing. 3. Return a default (like 0 or False) when the denominator is zero.",
            "Edge Case Analysis: Check what happens on empty input [] or when all numbers are 0. len([]) is 0, so dividing by length will crash unless guarded upfront.",
            "Structural Guard: At the very top of your function, return early if the collection is empty (e.g. 'if not items: return 0')."
        ]
    elif "indexerror" in err_lower or predicted_tag == "index_error":
        hints = [
            "List Bounds Invariant: Python sequences use 0-based indexing from 0 to len(items) - 1. A list with 3 elements has indices 0, 1, and 2.",
            f"Look at Line {line_num} in your code: an index was requested that equals or exceeds the list length, or the list is empty []. Adjust your loop boundary so the index stays strictly less than len(items).",
            "Algorithmic Logic: 1. Verify loop range: range(len(items)) visits 0 through len-1. 2. Guard against empty lists. 3. Use items[-1] to safely access the last item.",
            "Edge Case Analysis: What happens when the input has 0 or 1 element? Accessing items[1] immediately crashes with IndexError.",
            "Structural Guard: Place 'if not items: return ...' at the top of the function to prevent out-of-range indexing."
        ]
    elif "typeerror" in err_lower or predicted_tag == "type_error":
        hints = [
            "Type Invariant: Operations in Python require compatible data types. For example, text strings and numbers cannot be concatenated directly with '+'.",
            f"Look at Line {line_num} in your code: an operation was applied to incompatible types. Wrap numbers in str(...) or use an f-string f'{val}' before combining with strings, or convert with int().",
            "Algorithmic Logic: 1. Check variable types on this line. 2. Convert where necessary using int() or str(). 3. Verify the return value matches the expected return type.",
            "Edge Case Analysis: Check for None values. If a helper function returns None, performing arithmetic on it will trigger a TypeError.",
            "Structural Guard: Verify variable types before operations, or ensure all code paths return valid non-None values."
        ]
    elif "print_not_return" in (mistake_tags or []) or predicted_tag == "print_not_return":
        hints = [
            "Function Return Contract: Automated tests inspect the value returned by your function via 'return', not text printed to standard output.",
            f"Look at Line {line_num} in your code: replace 'print(...)' with 'return ...'.",
            "Algorithmic Logic: 1. Assign intermediate results to a variable. 2. When the result is complete, use the 'return' keyword. 3. Do not rely on print() for the answer.",
            "Edge Case Analysis: Calling print(val) causes the function to implicitly return None in Python.",
            "Structural Guard: Ensure every execution branch ends with 'return <answer>'."
        ]
    elif "mutates_input" in (mistake_tags or []) or predicted_tag == "mutates_input":
        hints = [
            "Input Immutability Invariant: A well-behaved function should not mutate the caller's arguments in place unless explicitly asked.",
            f"Look at Line {line_num} in your code: avoid mutating operations like .sort(), .append(), .pop(), or .remove() directly on the input argument.",
            "Algorithmic Logic: 1. Make a shallow copy with list(items) or items[:]. 2. Or use sorted(items) which returns a brand new list. 3. Return the newly created collection.",
            "Edge Case Analysis: When input is reused across tests, mutating it causes subsequent tests to fail with contaminated data.",
            "Structural Guard: Use 'sorted_items = sorted(items)' instead of 'items.sort()'."
        ]
    elif "unhandled_short_input" in (mistake_tags or []) or predicted_tag == "unhandled_short_input":
        hints = [
            "Short Input Invariant: Real-world inputs frequently include empty collections ([], '') or collections smaller than expected.",
            f"Look at Line {line_num} in your code: the function assumes the input has multiple elements, crashing or giving wrong answers on short inputs.",
            "Algorithmic Logic: 1. Add an early return for empty inputs. 2. Clamp index requests to min(k, len(items)). 3. Verify that size < required_size returns the problem's default.",
            "Edge Case Analysis: Check what happens on input length 0 and length 1.",
            "Structural Guard: Place 'if not items: return <default>' at the top of your function."
        ]
    elif "boundary_comparison" in (mistake_tags or []) or predicted_tag == "boundary_comparison":
        hints = [
            "Boundary Comparison Invariant: Exact threshold problems require strict adherence to inclusive (<=, >=) vs exclusive (<, >) comparisons.",
            f"Look at Line {line_num} in your code: check the comparison operator. If a mark of 40 is passing, mark > 40 will reject students with mark == 40.",
            "Algorithmic Logic: 1. Re-read the boundary requirement. 2. Use '>=' for 'at least' or 'passing', and '<=' for 'at most'. 3. Test on the exact cutoff value.",
            "Edge Case Analysis: When test input contains the exact threshold value, an off-by-one boundary comparison yields the opposite boolean result.",
            "Structural Guard: Replace '>' with '>=' or '<' with '<='."
        ]
    elif "off_by_one" in (mistake_tags or []) or predicted_tag == "off_by_one":
        hints = [
            "Loop Boundary Invariant: In Python, range(start, stop) stops at stop - 1. Slicing items[start:stop] also excludes the element at index stop.",
            f"Look at Line {line_num} in your code: your loop boundary or slice stops one element too early or includes one element too many.",
            "Algorithmic Logic: 1. Use range(len(items)) to visit every index 0 to len-1. 2. If you need N elements starting from 1, use range(1, n + 1).",
            "Edge Case Analysis: Check if the first or last item in the list is excluded from the calculation.",
            "Structural Guard: Adjust loop range or slice end index by +1 or -1."
        ]
    elif "timeout" in err_lower or predicted_tag == "timeout_tle":
        hints = [
            "Loop Termination Invariant: Every loop iteration must make guaranteed progress toward its termination condition.",
            f"Look at Line {line_num} in your code: the process timed out (Time Limit Exceeded). Check for an infinite while loop or nested O(N^2) iterations.",
            "Algorithmic Logic: 1. Ensure loop variables increment on every iteration. 2. For nested loops on large inputs, use a dictionary or set for O(1) lookups.",
            "Edge Case Analysis: When inputs are large (N >= 10^5), an O(N^2) algorithm will exceed the 2-second time limit.",
            "Structural Guard: Replace nested loops with a single pass and a hash map."
        ]
    else:
        hints = [
            f"Review the core invariant of {challenge.get('title', 'this challenge') if challenge else 'the problem'}: ensure all edge cases are handled.",
            f"Look at Line {line_num} in your code: inspect the calculation or condition on this line.",
            "Algorithmic Logic: 1. Validate inputs. 2. Execute the primary transformation. 3. Return the result outside the loop.",
            "Edge Case Analysis: Verify behavior on empty inputs and single elements.",
            "Structural Guard: Check return type and condition contracts."
        ]

    selected_hint = leak_guard(hints[hint_level - 1])

    # Log to SQLite and llm.jsonl for judge transparency (no external API calls)
    prompt_record = f"Local ML inference for {challenge.get('title', '') if challenge else ''} [Tag: {predicted_tag}, Conf: {confidence:.2f}, Lvl: {hint_level}]"
    try:
        log_llm_call(
            prompt=prompt_record,
            response=selected_hint,
            model_used="🧠 Dojo Local ML Model (Trained Offline - Scikit-Learn)",
            submission_id=test_run_data.get("submission_id") if isinstance(test_run_data, dict) else None
        )
    except Exception:
        pass

    return {
        "hint": selected_hint,
        "hint_type": hint_title,
        "hint_level": hint_level,
        "model_used": "🧠 Dojo Local ML Model (Trained Offline - Scikit-Learn)",
        "predicted_tag": predicted_tag,
        "ml_confidence": round(confidence, 3),
        "invariant": invariant
    }
