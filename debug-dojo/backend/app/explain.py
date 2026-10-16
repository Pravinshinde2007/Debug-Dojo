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

    # If it failed on a specific KIND of test case, refer to the kind in plain English
    explanation_parts = []

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


def get_progressive_hints(challenge: Dict[str, Any], mistake_tags: List[str], test_run_data: Dict[str, Any]) -> List[str]:
    """
    Builds the 4 progressive hint levels for a failure.
    Level 1: General concept
    Level 2: Where to investigate
    Level 3: Underlying cause
    Level 4: Debugging strategy
    """
    challenge_id = challenge.get("id", "")
    challenge_hints = challenge.get("hints", {})

    # Check if challenge has pre-authored custom hints
    if isinstance(challenge_hints, list) and len(challenge_hints) >= 4:
        return [leak_guard(h) for h in challenge_hints[:4]]

    # Otherwise synthesize progressive hints based on mistake tags and challenge
    hints = []

    if "print_not_return" in mistake_tags:
        hints = [
            "In Python functions, producing console output is distinct from delivering data to the program that called the function.",
            "Inspect the last statement of your function body. Look at whether you are printing or returning.",
            "The calling test expects to receive an object via 'return', but currently receives None because print() has no return value.",
            "Replace the call to print(...) with a return statement that hands the computed value back to the caller."
        ]
    elif "mutates_input" in mistake_tags:
        hints = [
            "Functions that process collections should ideally avoid side-effects on their input arguments.",
            "Look for list methods that remove elements or alter the list directly (such as .pop(), .remove(), or del).",
            "When you mutate the argument in-place, subsequent tests or callers find the original data destroyed.",
            "Instead of modifying the argument list, use slicing or build a fresh result list to return."
        ]
    elif "unhandled_short_input" in mistake_tags:
        hints = [
            "Algorithms must guard against inputs that are smaller than the standard case or completely empty.",
            "Check what happens before entering your main loop or calculation: what if the input length is 0 or less than expected?",
            "Attempting to slice with negative indices or access indices without checking length can trigger unexpected behavior.",
            "Add a guard clause at the very beginning of your function that explicitly checks for empty collections or non-positive sizes."
        ]
    elif "boundary_comparison" in mistake_tags:
        hints = [
            "Threshold decisions often hinge on whether a value meeting the exact boundary is included or excluded.",
            "Examine your relational comparison operators (such as '>' versus '>=') inside the condition.",
            "A student with a score exactly equal to the pass mark should qualify, but strict inequality treats them as failed.",
            "Change the strict comparison to an inclusive comparison so that values exactly matching the boundary are counted."
        ]
    elif "off_by_one" in mistake_tags:
        hints = [
            "Loop ranges and slices in Python use half-open intervals: the upper boundary is excluded.",
            "Trace the start and stop arguments of your range(...) or slice [start:stop].",
            "If your range starts at 0 instead of 1, or stops one item too early, your list will either miss the final item or include an unwanted zero.",
            "Adjust the range start or stop parameter by 1 so the sequence covers precisely the intended elements."
        ]
    else:
        hints = [
            "Review the problem specification carefully and consider what assumptions your logic makes about the inputs.",
            "Check the variable initialization and the condition governing when the computation ends.",
            "Trace your code manually on a 2-element example to verify the intermediate values.",
            "Add temporary assertions or verify that each edge case (0, 1, empty) produces the desired output."
        ]

    # Ensure all hints pass leak guard
    return [leak_guard(h) for h in hints]
