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
    Uses clear, beginner-friendly terms.
    """
    if test_run_data.get("all_passed", True):
        return "All tests passed! Excellent work solving the challenge."

    first_error = test_run_data.get("first_error")
    if first_error and first_error.get("error_type"):
        line_part = f" on line {first_error.get('error_line')}" if first_error.get("error_line") else ""
        err_msg = first_error.get("error_msg", "")
        return f"Python stopped with an error ({first_error.get('error_type')}){line_part}: {err_msg}"

    first_failed = test_run_data.get("first_failed_test")
    if first_failed:
        outcome = first_failed.get("outcome")
        if outcome == "timeout":
            return "Your code took too long to finish (over 2.0s). Check if your while or for loop is running infinitely."
        if first_failed.get("kind"):
            return f"Your code passed the visible tests, but did not work on the edge case: {first_failed.get('kind')}."
        if outcome == "wrong_output" and first_failed.get("call"):
            return f"Test #{first_failed.get('test', 1)} returned the wrong result: calling {first_failed.get('call')} gave {first_failed.get('got')} instead of {first_failed.get('expected')}."

    detailed_tests = test_run_data.get("_detailed_data", [])
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
        return "Your code took too long to finish. Make sure any loops have a condition that lets them stop."

    if "print_not_return" in mistake_tags:
        return "Your function displays output to the screen with print(), but does not return a value back to the test."

    if "mutates_input" in mistake_tags:
        return "Your function modifies the input list directly. The challenge requires calculating the answer without altering the original list."

    if "unhandled_short_input" in mistake_tags:
        if kind:
            return f"Your code works on standard examples, but fails when given: {kind}."
        return "Your code works on standard examples, but fails on small or empty inputs (like an empty list [])."

    if "boundary_comparison" in mistake_tags:
        return "Your logic is very close, but has a cutoff comparison mistake right at the threshold value (e.g. > vs >=)."

    if "off_by_one" in mistake_tags:
        return "Your function's result is off by one item or step. Check where your loop or slice starts and ends."

    if kind:
        return f"Your solution did not pass on: {kind}."

    return "A test case did not produce the expected result. Check your loop boundaries and return condition."


def get_progressive_hints(
    challenge: Dict[str, Any],
    mistake_tags: List[str],
    test_run_data: Dict[str, Any],
    code: str = ""
) -> List[str]:
    """
    Builds beginner-friendly, progressive hints tailored to the learner's code:
    - Beginner (Easy): 5 hints
    - Intermediate (Medium): 4 hints
    - Advanced (Hard): 3 hints

    Hint 2 dynamically highlights the exact Line number in the learner's code.
    """
    difficulty = str(challenge.get("difficulty") or "Easy").lower()
    max_hints = 5 if difficulty in ("easy", "beginner") else 4 if difficulty in ("medium", "intermediate") else 3

    # Extract error line if an exception occurred
    error_line = None
    first_error = test_run_data.get("first_error") if isinstance(test_run_data, dict) else None
    if first_error:
        error_line = first_error.get("error_line")

    # If no crash line, inspect code to find active return, loop, if, or pass statement
    if not error_line and code:
        lines = code.split("\n")
        for idx, l in enumerate(lines, 1):
            s = l.strip()
            if s.startswith("return ") or s.startswith("if ") or s.startswith("for ") or s.startswith("while ") or s == "pass" or s.startswith("pass"):
                error_line = idx
                break
        if not error_line:
            error_line = 2 if len(lines) >= 2 else 1
    elif not error_line:
        error_line = 2

    first_failed = test_run_data.get("first_failed_test", {}) if isinstance(test_run_data, dict) else {}
    kind = first_failed.get("kind", "")

    # Beginner-friendly line guidance
    where_to_look = f"Look at Line {error_line} in your code: inspect the calculation, loop, or condition on this line."

    # Check if challenge has pre-authored custom hints
    challenge_hints = challenge.get("hints", [])
    if isinstance(challenge_hints, list) and len(challenge_hints) > 0:
        hints = list(challenge_hints)
        # Ensure Hint 2 directs the student to their code line
        if len(hints) >= 2:
            if not hints[1].startswith("Look at Line"):
                hints[1] = f"Look at Line {error_line} in your code: {hints[1]}"
        else:
            hints.append(where_to_look)

        # Pad up to max_hints if needed
        fallbacks = [
            f"Pay special attention to edge cases: what should happen when given {kind or 'an empty list [] or size 0'}?",
            "Make sure your return statement is outside the loop and returns the final calculated answer.",
            "Test your logic step-by-step with a 2-element example on paper."
        ]
        for fb in fallbacks:
            if len(hints) < max_hints:
                hints.append(fb)

        return [leak_guard(h) for h in hints[:max_hints]]

    # Synthesize hints based on mistake tags and code inspection
    if "print_not_return" in mistake_tags:
        hints = [
            "In Python, print() only shows text on your screen. The test expects your function to return the value with 'return'.",
            f"Look at Line {error_line} in your code: check if you are calling print(...) instead of returning the result.",
            "Because print() does not send data back, the test received None instead of the expected answer.",
            "Functions must use the 'return' keyword so the calling code can receive and check the answer.",
            "Replace your print(...) statement with 'return' followed by the variable containing the answer."
        ]
    elif "mutates_input" in mistake_tags:
        hints = [
            "This problem requires finding the answer without changing the original input list.",
            f"Look at Line {error_line} in your code: check methods like .pop(), .remove(), or del that modify the input list in-place.",
            "When you alter the original list directly, subsequent tests or callers find their data destroyed.",
            "Instead of changing the input list, create a brand-new list to hold your results.",
            "Build and return a fresh new list, leaving the original input unchanged."
        ]
    elif "unhandled_short_input" in mistake_tags:
        hints = [
            "Your code works on normal cases, but needs to handle empty or very small inputs without errors.",
            f"Look at Line {error_line} in your code: what happens on this line if the input list is completely empty []?",
            f"Boundary check: test what happens when the input is {kind or 'empty or has fewer elements than expected'}.",
            "Trying to access items by index or slice without checking length first can cause unexpected errors.",
            "Add a quick check at the start of your function (e.g. 'if not nums: return 0' or appropriate default) to handle empty inputs right away."
        ]
    elif "boundary_comparison" in mistake_tags:
        hints = [
            "Check your comparison condition: make sure values that exactly match the threshold are included or excluded properly.",
            f"Look at Line {error_line} in your code: check if you wrote '>' when you meant '>=', or '<' when you meant '<='.",
            "For example, if 40 is a passing score, a score of exactly 40 must pass. '>' skips 40, whereas '>=' includes it.",
            "Strict comparisons (> and <) do not include the cutoff number itself.",
            "Update your condition to use '>=' or '<=' so values right on the boundary are counted."
        ]
    elif "off_by_one" in mistake_tags:
        hints = [
            "Your loop or slice is off by one item. Remember that Python indexing starts at 0, and ranges stop before the end number.",
            f"Look at Line {error_line} in your code: inspect your range(start, stop) numbers or slice [start:stop].",
            "In Python, range(5) produces 0, 1, 2, 3, 4 (it excludes 5). If you need 1 to 5, use range(1, 6).",
            "Stopping one step too early misses the last item; starting at 0 instead of 1 adds an extra item.",
            "Adjust your start or stop value by adding or subtracting 1 so the sequence covers the exact items needed."
        ]
    else:
        hints = [
            "Review what the function is asked to do and what it should return for simple examples.",
            where_to_look,
            f"Think about edge cases: how should your function behave on {kind or 'an empty input, 0, or single-element list'}?",
            "Trace the values of your variables step-by-step through one loop iteration.",
            "Make sure your return statement is placed outside the loop so it only returns after all items are processed."
        ]

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
    for learner-pasted Python code. Guaranteed zero code leakage via leak_guard.
    """
    if not error_type and not error_msg:
        return {
            "explanation": "Your code ran completely without any crashes or errors! Check the terminal output on the left to confirm it matches what you wanted.",
            "hints": [
                "Your program finished running without throwing any errors.",
                "Review the printed output in the terminal to ensure the output is correct.",
                "Consider trying edge cases, such as empty inputs, 0, or negative numbers.",
                "You solved the bug! You can now move on to another challenge or paste more code."
            ]
        }

    err_str = str(error_type or error_msg or "").lower()
    line_ref = f" on line {error_line}" if error_line else ""

    if "syntax" in err_str:
        explanation = f"Your code has a Syntax Error{line_ref}. Python could not understand this line because of a missing or misplaced character."
        hints = [
            "Syntax errors happen when code breaks Python's grammar rules, like a missing colon or parenthesis.",
            f"Look at line {error_line or 'where the error occurred'} and the line immediately before it.",
            "Check for missing colons ':' at the end of 'if', 'for', 'while', or 'def' statements, or unclosed quotes/brackets.",
            "Ensure every opening bracket (, [, { has a matching closing bracket, and compound headers end with ':'."
        ]
    elif "indent" in err_str or "tab" in err_str:
        explanation = f"Your code has an Indentation Error{line_ref}. In Python, spaces at the start of a line show which lines belong inside a function or loop."
        hints = [
            "Python uses indentation (4 spaces) instead of curly braces to group code inside functions, loops, and ifs.",
            f"Look at line {error_line or 'the error line'} and check the spacing at the start of that line.",
            "Lines inside a function, loop, or if-statement must be indented further than the header line.",
            "Use consistent 4 spaces for each indentation level and avoid mixing tabs and spaces."
        ]
    elif "zerodivision" in err_str:
        explanation = f"Your code tried to divide by zero{line_ref}. In math, dividing by 0 is not allowed, so Python stopped with an error."
        hints = [
            "A number cannot be divided by zero.",
            f"Look at line {error_line or 'the active line'}: find where the division operator (/ or // or %) is used.",
            "This often happens when dividing by len(my_list) when the list happens to be empty (length 0).",
            "Add an if-check before the division (e.g. 'if count != 0:') to handle the zero case safely without crashing."
        ]
    elif "indexerror" in err_str or "range" in err_str:
        explanation = f"Your code tried to access an item that does not exist in the list or string{line_ref}."
        hints = [
            "Python lists and strings start at index 0. For example, a list with 3 items has indices 0, 1, and 2.",
            f"Check which list or string is being accessed on line {error_line or 'the error line'}.",
            "If your loop index reaches the list length or higher, it triggers an IndexError.",
            "Make sure your loop stops before reaching the end, or check if the list is empty before accessing it."
        ]
    elif "typeerror" in err_str:
        explanation = f"Your code tried to combine or use incompatible data types{line_ref}."
        hints = [
            "In Python, different data types (numbers, text strings, lists, None) have specific operations they support.",
            f"Check the types of the variables used in the operation on line {error_line or 'the error line'}.",
            "For example, you cannot add a number to text ('hello' + 5), or iterate over a number with 'for x in 10:'.",
            "Convert values using int() or str(), or check if a variable is None before trying to use it."
        ]
    elif "nameerror" in err_str:
        explanation = f"Your code tried to use a variable or function name{line_ref} that has not been created yet."
        hints = [
            "Python must see a variable's assignment before you can use that variable.",
            f"Check the exact spelling and capitalization of the name on line {error_line or 'the error line'}.",
            "Look for small typos, or check if the variable was created inside an if-block that didn't run.",
            "Initialize or define the variable before the line where you use it."
        ]
    elif "keyerror" in err_str:
        explanation = f"Your code tried to look up a key that does not exist in the dictionary{line_ref}."
        hints = [
            "Dictionaries only return values for keys that are currently stored in them.",
            f"Check the dictionary key being looked up on line {error_line or 'the active line'}.",
            "Directly accessing my_dict[key] when the key is missing causes a KeyError.",
            "Use 'if key in my_dict:' to check beforehand, or use 'my_dict.get(key, default)'."
        ]
    elif "timeout" in err_str:
        explanation = "Your code ran for too long (over 2.0 seconds). This almost always means a while or for loop is running forever in an infinite loop."
        hints = [
            "Every loop must have a condition that eventually becomes false so the loop can stop.",
            "Check all 'while' loops in your code: is the counter or condition variable being updated inside the loop?",
            "Make sure the variable controlling the loop changes on every iteration.",
            "Step through your loop on paper with sample numbers to make sure the loop reaches its end."
        ]
    elif "outputlimit" in err_str:
        explanation = "Your code printed too much text to the terminal. This usually happens when print() is inside an infinite loop."
        hints = [
            "Programs must not flood the screen with thousands of print statements.",
            "Check if you have a print() statement inside a loop that is running too many times.",
            "Ensure the loop finishes promptly, or remove unnecessary print calls.",
            "Only print what is needed to verify your result."
        ]
    else:
        explanation = f"Your code stopped due to {error_type or 'a Python error'}{line_ref} ({error_msg or 'exception raised'})."
        hints = [
            "An unhandled error stopped your code from finishing.",
            f"Inspect the operations on line {error_line or 'where the error occurred'}.",
            "Check the values and types of variables right before this line runs.",
            "Add defensive checks (like checking for empty lists or None) to handle edge cases safely."
        ]

    return {
        "explanation": explanation,
        "hints": [leak_guard(h) for h in hints]
    }
