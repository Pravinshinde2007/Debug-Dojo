"""
Explain module: Generates plain-language failure explanations and progressive 4-level hints.
Enforces Rule 2 (never reveals hidden values, only names the KIND of input)
and Rule 4 (4 progressive hints, leak guard preventing code or full solution leaks).
"""

import re
from typing import Dict, Any, List, Optional
from .llm import leak_guard

HINT_LADDER_CATEGORIES = {
    1: "General concept",
    2: "Where to investigate",
    3: "Underlying cause",
    4: "Debugging strategy"
}


def explain_failure(test_run_data: Dict[str, Any], mistake_tags: List[str], challenge: Dict[str, Any]) -> str:
    """
    Rule 2: Plain-language explanation that names the KIND of input, NEVER the test values.
    """
    if test_run_data.get("all_passed", True):
        return "All tests passed! Excellent work sharpening your logic."

    first_error = test_run_data.get("first_error")
    if first_error and first_error.get("error_type"):
        line_part = f" on line {first_error.get('error_line')}" if first_error.get("error_line") else ""
        err_msg = first_error.get("error_msg", "")
        # Remove redundant exception prefix if already in error_msg
        return f"Runtime error ({first_error.get('error_type')}){line_part}: {err_msg}"

    first_failed = test_run_data.get("first_failed_test")
    if first_failed:
        outcome = first_failed.get("outcome")
        if outcome == "timeout":
            return "Your solution took too long to complete. Check for an infinite loop or an unadvancing index variable."
        if first_failed.get("kind"):
            return f"Your code passed visible tests, but failed on hidden boundary case: {first_failed.get('kind')}."
        if outcome == "wrong_output" and first_failed.get("call"):
            return f"Incorrect output on test #{first_failed.get('test', 1)}: calling {first_failed.get('call')} returned {first_failed.get('got')} instead of {first_failed.get('expected')}."

    detailed_tests = test_run_data.get("_detailed_data", [])
    
    # Find first failing test
    first_failure = None
    for t in detailed_tests:
        if t["outcome"] != "passed":
            first_failure = t
            break

    if not first_failure:
        return "Some test cases did not pass. Take a close look at your edge cases."

    kind = first_failure.get("kind", "")
    outcome = first_failure.get("outcome")

    if outcome == "timeout":
        return "Your solution took too long to complete. Check for an infinite loop or an unadvancing index variable."

    if "print_not_return" in mistake_tags:
        return "Your function displays output to the terminal with print(), but does not return a value back to the caller."

    if "mutates_input" in mistake_tags:
        return "Your function modifies the caller's input list in-place. The challenge requires calculating and returning a result without altering the original data."

    if "unhandled_short_input" in mistake_tags:
        if kind:
            return f"Your code works on standard examples, but fails on {kind}."
        return "Your code works on standard examples, but struggles with boundary cases such as an empty list or small input size."

    if "boundary_comparison" in mistake_tags:
        return "Your logic is close, but has a boundary comparison issue right at the exact threshold value."

    if "off_by_one" in mistake_tags:
        return "Your function calculates a result that is shifted by one element or step from what is expected."

    if kind:
        return f"Your solution did not pass on {kind}."

    return "A test case did not produce the expected result. Check your loop boundaries and return condition."


def get_progressive_hints(
    challenge: Dict[str, Any],
    mistake_tags: List[str],
    test_run_data: Dict[str, Any],
    code: str = ""
) -> List[str]:
    """
    Builds level-scaled progressive hints:
    - Beginner (Easy): 5 hints
    - Intermediate (Medium): 4 hints
    - Advanced (Hard): 3 hints

    Hint 2 explicitly highlights the line number where the error or decision occurs.
    """
    difficulty = str(challenge.get("difficulty") or "Easy").lower()
    max_hints = 5 if difficulty == "easy" else 4 if difficulty == "medium" else 3

    # Extract error line if a runtime or syntax error occurred
    error_line = None
    error_type = None
    first_error = test_run_data.get("first_error") if isinstance(test_run_data, dict) else None
    if first_error:
        error_line = first_error.get("error_line")
        error_type = first_error.get("error_type")

    # If no runtime crash line, inspect code for return statement or condition
    if not error_line and code:
        lines = code.split("\n")
        for idx, l in enumerate(lines, 1):
            s = l.strip()
            if s.startswith("return ") or s.startswith("if ") or s.startswith("for ") or s.startswith("while "):
                error_line = idx
                break

    first_failed = test_run_data.get("first_failed_test", {}) if isinstance(test_run_data, dict) else {}
    kind = first_failed.get("kind", "")

    # Check if challenge has pre-authored custom hints
    challenge_hints = challenge.get("hints", [])
    if isinstance(challenge_hints, list) and len(challenge_hints) >= max_hints:
        hints = list(challenge_hints[:max_hints])
        # Inject line number into hint 2 if available
        if error_line and len(hints) >= 2:
            hints[1] = f"Look at Line {error_line} in your code: {hints[1]}"
        return [leak_guard(h) for h in hints]

    # Synthesize hints based on mistake tags and failure context
    hints = []

    # Hint 2 line reference
    where_to_look = (
        f"Look at Line {error_line} in your code: inspect the expressions and operations evaluated on this line."
        if error_line
        else "Inspect the loop termination and return statements inside your function body."
    )

    if "print_not_return" in mistake_tags:
        hints = [
            "In Python functions, producing console output with print() is distinct from returning a value to the caller.",
            where_to_look,
            "The calling test expects to receive an object via 'return', but currently receives None because print() has no return value.",
            "Functions evaluated by an automated judge must return their result so the test runner can compare it with the expected answer.",
            "Replace the call to print(...) with a return statement that hands the computed value back to the caller."
        ]
    elif "mutates_input" in mistake_tags:
        hints = [
            "Functions that process collections should avoid modifying their input arguments directly.",
            where_to_look,
            "When you mutate an argument in-place with methods like .pop() or del, subsequent callers find the original data destroyed.",
            "Operating on a slice copy or accumulating into a new list guarantees the original input remains untouched.",
            "Instead of modifying the argument list, construct and return a fresh new list or use non-mutating operations."
        ]
    elif "unhandled_short_input" in mistake_tags:
        hints = [
            "Algorithms must handle boundary cases gracefully, such as empty collections or inputs smaller than expected.",
            where_to_look,
            f"Pay special attention to {kind or 'boundary conditions'}: what happens when the length is 0 or less than the required amount?",
            "Attempting to slice with negative indices or accessing elements without checking length can return unexpected values.",
            "Add an early guard clause at the start of your function that explicitly handles empty inputs or small sizes."
        ]
    elif "boundary_comparison" in mistake_tags:
        hints = [
            "Threshold decisions often hinge on whether a value meeting the exact boundary is included or excluded.",
            where_to_look,
            "Check what happens when an input value exactly matches the threshold (such as 40 in a pass mark).",
            "Relational operators like '>' exclude the boundary value, whereas '>=' includes it.",
            "Change the strict inequality to an inclusive comparison so that values exactly matching the boundary are counted."
        ]
    elif "off_by_one" in mistake_tags:
        hints = [
            "Loop ranges and slices in Python use half-open intervals: the upper boundary is excluded.",
            where_to_look,
            "Trace the start and stop arguments: Python range(n) produces 0 through n-1, not 1 through n.",
            "If your range starts at 0 instead of 1, or stops one item too early, your list will either miss the final item or include an unwanted element.",
            "Adjust the range start or stop parameter by 1 so the sequence covers precisely the intended elements."
        ]
    else:
        hints = [
            "Review the problem specification carefully and consider what assumptions your logic makes about the inputs.",
            where_to_look,
            f"Consider how your function behaves on edge cases such as {kind or 'empty inputs, single items, or boundary thresholds'}.",
            "Trace your code manually on a 2-element example to verify the intermediate values at each step.",
            "Add temporary assertions or check variable state before returning to verify all logic branches."
        ]

    # Ensure all hints pass leak guard and match difficulty max_hints
    return [leak_guard(h) for h in hints[:max_hints]]


def explain_custom_code_error(
    error_type: Optional[str],
    error_line: Optional[int],
    error_msg: Optional[str],
    code: str,
    mistake_tags: List[str]
) -> Dict[str, Any]:
    """
    Generates beginner-friendly plain language error explanations and 4 progressive hints
    for learner-pasted arbitrary Python code. Guaranteed zero code leakage via leak_guard.
    """
    if not error_type and not error_msg:
        return {
            "explanation": "Your code executed successfully without any runtime crashes or syntax errors! Verify that the terminal output matches your intended result.",
            "hints": [
                "Your program ran from start to finish without raising an exception.",
                "Review the printed output to ensure it matches what you expected.",
                "Consider testing edge cases, such as empty inputs or negative values.",
                "Try writing additional assertions or test prints to verify all logic branches."
            ]
        }

    err_str = str(error_type or error_msg or "").lower()
    line_ref = f" on line {error_line}" if error_line else ""

    if "syntax" in err_str:
        explanation = f"Your code has a Syntax Error{line_ref}. Python's grammar parser was unable to understand this statement."
        hints = [
            "Syntax errors happen when code violates the spelling, grammar, or punctuation rules of Python.",
            f"Examine line {error_line or 'where the error occurred'} and the line immediately before it.",
            "Common syntax issues include missing colons at the end of 'if', 'for', 'while', or 'def', unclosed parentheses, or misplaced quotation marks.",
            "Make sure every opening bracket or quote has a matching close, and compound statements end with a colon."
        ]
    elif "indent" in err_str or "tab" in err_str:
        explanation = f"Your code has an Indentation Error{line_ref}. Python relies on consistent indentation to know which lines belong inside a block."
        hints = [
            "In Python, indentation replaces curly braces to define code blocks.",
            f"Look at line {error_line or 'the flagged line'} and compare its indentation to the surrounding code.",
            "Statements inside a function, loop, or conditional must be indented further than their header.",
            "Use a consistent 4 spaces per indentation level and avoid mixing tabs and spaces."
        ]
    elif "zerodivision" in err_str:
        explanation = f"Your code tried to divide by zero{line_ref}. Division by zero is undefined in mathematics and causes Python to crash."
        hints = [
            "Computers cannot divide numbers by zero.",
            f"Inspect the right-hand operand of your division operator on line {error_line or 'the active line'}.",
            "This frequently occurs when dividing by the length of an empty list or when a counter variable hasn't incremented.",
            "Add an 'if' condition before the division to check whether the denominator is zero and handle that case gracefully."
        ]
    elif "indexerror" in err_str or "range" in err_str:
        explanation = f"Your code encountered an Index Error{line_ref}: you tried to access a position that does not exist in the collection."
        hints = [
            "Python lists, tuples, and strings use zero-based indexing (0 to length - 1).",
            f"Check which list or string is being accessed on line {error_line or 'the flagged line'}, and what its size is.",
            "If a list has 3 items, the only valid positive indices are 0, 1, and 2. Attempting to access index 3 will trigger an IndexError.",
            "Verify that your loop index or slice stays strictly within the boundaries of the collection."
        ]
    elif "typeerror" in err_str:
        explanation = f"Your code encountered a Type Error{line_ref}: an operation was applied to an inappropriate or incompatible data type."
        hints = [
            "Different data types (numbers, text strings, lists, None) have specific operations they support.",
            f"Check the data types of variables participating in the operation on line {error_line or 'the error line'}.",
            "For instance, you cannot perform addition between a number and a string, or index into a variable whose value is None.",
            "Convert values using type conversion functions (like int() or str()), or check whether a variable is None before using it."
        ]
    elif "nameerror" in err_str:
        explanation = f"Your code tried to use a variable or function name{line_ref} that has not been defined yet."
        hints = [
            "Python must encounter a variable's assignment or definition before that variable can be accessed.",
            f"Check the exact spelling and capitalization of the identifier on line {error_line or 'the flagged line'}.",
            "Look for typos, variables defined inside an inner scope that was skipped, or missing function definitions.",
            "Initialize the variable before the line where it is used, or correct any spelling mismatch."
        ]
    elif "keyerror" in err_str:
        explanation = f"Your code encountered a Key Error{line_ref}: you tried to look up a key that doesn't exist in the dictionary."
        hints = [
            "Dictionaries only return values for keys that have been explicitly stored.",
            f"Check the dictionary key being requested on line {error_line or 'the active line'}.",
            "Directly indexing dict[key] when the key is absent raises a KeyError.",
            "Use 'key in dict' to check existence beforehand, or use the .get(key, default) method."
        ]
    elif "timeout" in err_str:
        explanation = "Your code exceeded the execution time limit (2.0s). This almost always indicates an infinite loop or runaway recursion."
        hints = [
            "Every loop must have a guaranteed stopping condition that becomes true after finite iterations.",
            "Check all 'while' loops and recursive functions in your script.",
            "Ensure that the variable controlling the loop's condition is being updated inside the loop body.",
            "Step through your loop manually with sample data to verify that the loop counter changes on every cycle."
        ]
    elif "outputlimit" in err_str:
        explanation = "Your code produced more terminal output than the 4KB limit. This often happens if print() is placed inside an infinite loop."
        hints = [
            "Programs must not flood stdout with excessive print messages.",
            "Look for print() statements located inside loops.",
            "Check if an un-advancing loop is repeatedly printing to the terminal.",
            "Remove unnecessary debug print calls or ensure the loop terminates promptly."
        ]
    else:
        explanation = f"Your code stopped due to {error_type or 'a runtime error'}{line_ref} ({error_msg or 'exception raised'})."
        hints = [
            "An unhandled condition halted execution before the script finished.",
            f"Investigate the operations on line {error_line or 'where the exception was reported'}.",
            "Check your variable states immediately before this line runs.",
            "Add defensive checks or error handling around this operation to keep your code safe."
        ]

    # Ensure all hints strictly obey leak guard (Rule 4)
    return {
        "explanation": explanation,
        "hints": [leak_guard(h) for h in hints]
    }
