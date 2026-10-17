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
        line_num = first_error.get("error_line")
        line_prefix = f"Line {line_num}: " if line_num else ""
        err_msg = first_error.get("error_msg", "")
        return f"{line_prefix}{first_error.get('error_type')} — {err_msg}"

    first_failed = test_run_data.get("first_failed_test")
    if first_failed:
        outcome = first_failed.get("outcome")
        if outcome == "timeout":
            return "Time Limit Exceeded (TLE): Your code took too long to finish (over 2.0s). Check if your while or for loop is running infinitely or if your time complexity needs optimization."
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
        if first_error.get("error_type"):
            err_hints_res = explain_custom_code_error(
                error_type=first_error.get("error_type"),
                error_line=error_line,
                error_msg=first_error.get("error_msg"),
                code=code,
                mistake_tags=mistake_tags
            )
            if err_hints_res.get("hints"):
                return [leak_guard(h) for h in err_hints_res["hints"][:max_hints]]

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
    Generates beginner-friendly, highly accurate plain language error explanations and
    4 progressive hints for learner-pasted Python code. Enforces zero code leakage via leak_guard.
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

    err_str = str(error_type or "").lower()
    msg_str = str(error_msg or "").lower()
    combined_err = f"{err_str} {msg_str}"
    line_ref = f" on line {error_line}" if error_line else ""

    lines = code.splitlines() if code else []
    line_idx = (error_line - 1) if (error_line and 0 < error_line <= len(lines)) else None
    line_text = lines[line_idx].strip() if line_idx is not None else ""

    # =========================================================================
    # 1. SYNTAX ERRORS
    # =========================================================================
    if "syntax" in combined_err:
        # Case 1A: Assignment inside return statement (e.g. return "Helo " = name or return x = 1)
        ret_match = re.search(r'\breturn\b\s+(.+?)\s*=\s*(.+)', line_text)
        if ret_match:
            left_part = ret_match.group(1).strip()
            right_part = ret_match.group(2).strip()
            is_str_lit = (left_part.startswith('"') and left_part.endswith('"')) or (left_part.startswith("'") and left_part.endswith("'"))
            if is_str_lit:
                return {
                    "explanation": f"Your code has a Syntax Error{line_ref}. An equals sign '=' was used where Python expected string concatenation or an expression.",
                    "hints": [
                        leak_guard("In Python, a single equals sign '=' is strictly for assigning values to variables (like 'x = 10'), not for combining text or expressions."),
                        leak_guard(f"Look at line {error_line}: inspect where '=' is placed after the return statement."),
                        leak_guard(f"You cannot assign to a text literal ({left_part}), nor can you put variable assignment inside a 'return' statement. If you want to combine text and a variable, use '+' (string concatenation) or an f-string."),
                        leak_guard("Replace '=' with '+' to join the strings together, or use an f-string.")
                    ]
                }
            else:
                return {
                    "explanation": f"Your code has a Syntax Error{line_ref}. You cannot place a variable assignment ('=') directly inside a 'return' statement.",
                    "hints": [
                        leak_guard("In Python, 'return' must be followed by a value or calculation expression, not an assignment statement."),
                        leak_guard(f"Look at line {error_line}: inspect where '=' is used after 'return'."),
                        leak_guard(f"If you want to assign to a variable, do the assignment on a separate line before the 'return' statement, or use '==' if checking equality."),
                        leak_guard("Move the variable assignment to its own line above, or change '=' to '==' if checking equality.")
                    ]
                }

        # Case 1B: Assignment to literal outside return (e.g. "Helo " = name or 5 = x)
        lit_assign = re.match(r'^(["\'].*?["\']|\d+(?:\.\d+)?)\s*=\s*(.+)', line_text)
        if lit_assign or "cannot assign to literal" in msg_str:
            lit_val = lit_assign.group(1) if lit_assign else "a literal value"
            return {
                "explanation": f"Your code has a Syntax Error{line_ref}. You cannot assign a value to a literal ({lit_val}).",
                "hints": [
                    leak_guard("In Python, the variable name must always be on the left side of '=', and the value or calculation on the right."),
                    leak_guard(f"Look at line {error_line}: inspect what is placed on the left side of '='."),
                    leak_guard(f"'{lit_val}' is a fixed value, not a variable name. In Python, assignment is always 'variable_name = value'."),
                    leak_guard("Put the variable name on the left side of '=', or use '+' or '==' if you meant concatenation or comparison.")
                ]
            }

        # Case 1C: Assignment in condition (e.g. if x = 5: or while count = 0:)
        if ("maybe you meant '=='" in msg_str or "cannot assign to expression" in msg_str or re.search(r'\b(if|while|elif)\b.+?=\s*[^=]', line_text)) and not re.search(r':=', line_text):
            return {
                "explanation": f"Your code has a Syntax Error{line_ref}. A single '=' was used in a condition where equality comparison ('==') was expected.",
                "hints": [
                    leak_guard("In Python, '=' assigns a value to a variable, while '==' compares two values to see if they are equal."),
                    leak_guard(f"Look at the condition on line {error_line}: find where the single '=' is located."),
                    leak_guard("Conditional statements like 'if', 'elif', and 'while' require a comparison. Using '=' tries to perform variable assignment instead of testing equality."),
                    leak_guard("Replace '=' with '==' to compare the values (for example: 'if x == 5:').")
                ]
            }

        # Case 1D: Non-Python logical / arithmetic operators (&&, ||, ++, --, !)
        if "&&" in line_text:
            return {
                "explanation": f"Your code has a Syntax Error{line_ref}. Python does not use '&&' for logical AND.",
                "hints": [
                    leak_guard("Python uses readable English words for logical operators instead of symbols like '&&'."),
                    leak_guard(f"Look at line {error_line} where '&&' is written."),
                    leak_guard("In Python, the logical AND operator is written as the word 'and'."),
                    leak_guard("Replace '&&' with 'and'.")
                ]
            }
        if "||" in line_text:
            return {
                "explanation": f"Your code has a Syntax Error{line_ref}. Python does not use '||' for logical OR.",
                "hints": [
                    leak_guard("Python uses readable English words for logical operators instead of symbols like '||'."),
                    leak_guard(f"Look at line {error_line} where '||' is written."),
                    leak_guard("In Python, the logical OR operator is written as the word 'or'."),
                    leak_guard("Replace '||' with 'or'.")
                ]
            }
        if re.search(r'\w\+\+|\+\+\w|\w--|--\w', line_text):
            return {
                "explanation": f"Your code has a Syntax Error{line_ref}. Python does not support '++' or '--' increment/decrement operators.",
                "hints": [
                    leak_guard("Python does not have '++' or '--' operators like C, Java, or JavaScript."),
                    leak_guard(f"Look at line {error_line} where the increment or decrement is attempted."),
                    leak_guard("To increase a variable by 1 in Python, use '+=' (e.g. 'count += 1') or 'count = count + 1'."),
                    leak_guard("Replace '++' with '+= 1' (or '--' with '-= 1').")
                ]
            }

        # Case 1E: Missing colon on compound statement header (def, if, elif, else, for, while, try, except, class)
        header_kws = ("def", "if", "elif", "else", "for", "while", "try", "except", "class", "with", "finally")
        first_token = line_text.split()[0] if line_text.split() else ""
        if "expected ':'" in msg_str or (first_token in header_kws and not line_text.endswith(":") and not line_text.endswith("\\")):
            return {
                "explanation": f"Your code has a Syntax Error{line_ref}. The '{first_token}' header statement is missing a colon ':' at the end.",
                "hints": [
                    leak_guard("In Python, compound statements that start a new code block must always end with a colon ':'."),
                    leak_guard(f"Look at the very end of line {error_line}."),
                    leak_guard(f"The '{first_token}' header statement requires a colon ':' at the end to tell Python where the indented block begins."),
                    leak_guard(f"Add a colon ':' at the end of line {error_line}.")
                ]
            }

        # Case 1F: Unclosed brackets or parentheses
        if "was never closed" in msg_str or "unclosed" in msg_str:
            bracket = "(" if "(" in msg_str else "[" if "[" in msg_str else "{" if "{" in msg_str else "bracket"
            return {
                "explanation": f"Your code has a Syntax Error{line_ref}. An opening {bracket} was never closed.",
                "hints": [
                    leak_guard(f"Every opening {bracket} in Python must have a matching closing pair."),
                    leak_guard(f"Check line {error_line} and any lines right before it."),
                    leak_guard(f"Look for a function call or list/dict expression that opened with '{bracket}' without a matching close."),
                    leak_guard(f"Add the missing closing bracket to complete the expression.")
                ]
            }

        # Case 1G: Unclosed string literal
        if "unterminated string literal" in msg_str or "eol while scanning" in msg_str:
            return {
                "explanation": f"Your code has a Syntax Error{line_ref}. A text string was started with quotes but never closed.",
                "hints": [
                    leak_guard("Text strings in Python must start and end with matching quotation marks (' or \")."),
                    leak_guard(f"Look at line {error_line}: check the quotation marks."),
                    leak_guard("A string literal is missing its closing quote before the end of the line."),
                    leak_guard("Add the matching closing quotation mark to close the string.")
                ]
            }

        # Case 1H: Return outside function
        if "'return' outside function" in msg_str:
            return {
                "explanation": f"Your code has a Syntax Error{line_ref}. The 'return' keyword can only be used inside a function definition ('def').",
                "hints": [
                    leak_guard("'return' is used inside a function to return a value to the caller."),
                    leak_guard(f"Look at line {error_line}: 'return' is placed at the top level of the file."),
                    leak_guard("Top-level code cannot return. If you want to show a value on screen, use 'print()', or wrap your code in a 'def' function."),
                    leak_guard("Either wrap the code inside a 'def' function, or replace 'return' with 'print()'.")
                ]
            }

        # Case 1I: Python 2 style print statement
        if "missing parentheses in call to 'print'" in msg_str or re.match(r'^print\s+["\']', line_text):
            return {
                "explanation": f"Your code has a Syntax Error{line_ref}. In Python 3, print is a function and requires parentheses: print(...).",
                "hints": [
                    leak_guard("In Python 3, print is a built-in function, not a statement keyword."),
                    leak_guard(f"Look at line {error_line}: check the print statement."),
                    leak_guard("The text or variable being printed must be enclosed inside parentheses."),
                    leak_guard("Wrap the arguments in parentheses: print(...).")
                ]
            }

        # Default SyntaxError fallback (context-aware, does NOT falsely claim missing colons)
        return {
            "explanation": f"Your code has a Syntax Error{line_ref}: Python could not understand this line ({error_msg or 'invalid syntax'}).",
            "hints": [
                leak_guard("Syntax errors occur when code breaks Python's grammar rules, such as misplaced operators or keywords."),
                leak_guard(f"Look at line {error_line or 'where the error occurred'}: inspect the exact characters and operators on this line."),
                leak_guard("Check that variable names, operators, brackets, and quotes follow standard Python rules."),
                leak_guard("Review the structure of this line to make sure all statements and expressions are valid.")
            ]
        }

    # =========================================================================
    # 2. INDENTATION / TAB ERRORS
    # =========================================================================
    if "indent" in combined_err or "taberror" in combined_err or "inconsistent use of tabs" in msg_str:
        if "expected an indented block" in msg_str:
            return {
                "explanation": f"Your code has an Indentation Error{line_ref}. Python expected an indented block of code after a statement ending with ':'.",
                "hints": [
                    leak_guard("In Python, any statement ending with ':' (like def, if, for, while) must be followed by indented lines."),
                    leak_guard(f"Look at line {error_line} and the line directly above it."),
                    leak_guard("The body of functions, loops, and conditions must be indented with 4 spaces."),
                    leak_guard("Add 4 spaces at the beginning of this line (or add 'pass' if you want an empty block).")
                ]
            }
        elif "unexpected indent" in msg_str:
            return {
                "explanation": f"Your code has an Indentation Error{line_ref}. This line has extra spaces at the start that do not match any block header.",
                "hints": [
                    leak_guard("Lines should only be indented if they belong inside an active block header (like def, if, for, while)."),
                    leak_guard(f"Look at the beginning of line {error_line}."),
                    leak_guard("This line has extra leading spaces, but there is no statement above it that opened a new block."),
                    leak_guard("Remove the extra spaces from the start of the line so it aligns with surrounding code.")
                ]
            }
        elif "inconsistent use of tabs and spaces" in msg_str or "taberror" in combined_err:
            return {
                "explanation": f"Your code has a Tab / Indentation Error{line_ref}. You are mixing tabs and spaces for indentation.",
                "hints": [
                    leak_guard("Python 3 forbids mixing tab characters and space characters for indentation in the same file."),
                    leak_guard(f"Check line {error_line} for invisible tab characters mixed with spaces."),
                    leak_guard("Different editors interpret tabs differently, which can cause subtle indentation mismatches."),
                    leak_guard("Standardize your entire code to use 4 regular spaces per indent level.")
                ]
            }
        return {
            "explanation": f"Your code has an Indentation Error{line_ref}. Python uses indentation (4 spaces) to organize blocks of code.",
            "hints": [
                leak_guard("Python relies on consistent indentation instead of curly braces to group code inside functions and loops."),
                leak_guard(f"Check the spacing at the start of line {error_line}."),
                leak_guard("Ensure each block is indented by exactly 4 spaces further than the line that started it."),
                leak_guard("Align this line with the appropriate outer block level.")
            ]
        }

    # =========================================================================
    # 3. TYPE ERRORS
    # =========================================================================
    if "typeerror" in combined_err:
        if "can only concatenate str" in msg_str or "unsupported operand type(s) for +: 'int' and 'str'" in msg_str or "unsupported operand type(s) for +: 'str' and 'int'" in msg_str:
            return {
                "explanation": f"Your code has a Type Error{line_ref}. You cannot add or concatenate a text string and a number directly.",
                "hints": [
                    leak_guard("In Python, the '+' operator does addition for numbers, but concatenation for strings. It cannot combine both without conversion."),
                    leak_guard(f"Look at line {error_line}: find where '+' is used between a string and a number."),
                    leak_guard("Python does not automatically convert numbers to text. You must explicitly convert the number using 'str()' or an f-string."),
                    leak_guard("Wrap the number in 'str(num)' or use an f-string to combine the text.")
                ]
            }
        elif "'nonetype' object is not subscriptable" in msg_str or "'nonetype' object" in msg_str:
            return {
                "explanation": f"Your code has a Type Error{line_ref}. A variable holding 'None' was used as if it were a list, dictionary, or object.",
                "hints": [
                    leak_guard("'None' is a special Python value indicating the absence of data."),
                    leak_guard(f"Look at the variable being accessed on line {error_line}."),
                    leak_guard("This variable evaluated to 'None'. This often happens when a function forgot to 'return' a value, or a method like list.sort() was assigned to a variable."),
                    leak_guard("Ensure the function returns data, or check 'if var is not None:' before indexing into it.")
                ]
            }
        elif "is not callable" in msg_str:
            target = "a number or string"
            if "'int' object" in msg_str: target = "an integer"
            elif "'str' object" in msg_str: target = "a string"
            elif "'list' object" in msg_str: target = "a list"
            return {
                "explanation": f"Your code has a Type Error{line_ref}. You tried to call {target} as if it were a function.",
                "hints": [
                    leak_guard("Placing parentheses '()' after a variable tells Python to execute it as a function."),
                    leak_guard(f"Look at line {error_line}: check which variable has parentheses '()' after it."),
                    leak_guard(f"The variable holds {target}, not a function. This often occurs if you named a variable the same as a built-in function (like 'sum = 5'), or forgot a '*' multiplication operator."),
                    leak_guard("Rename any variables that conflict with function names, or add the missing '*' multiplication operator.")
                ]
            }
        elif "is not iterable" in msg_str:
            return {
                "explanation": f"Your code has a Type Error{line_ref}. You tried to loop over or unpack a non-iterable value (like a single number).",
                "hints": [
                    leak_guard("'for' loops and sequence functions require an iterable collection (like a list, string, or range), not a single number."),
                    leak_guard(f"Look at line {error_line}: inspect the variable in your 'for ... in ...' loop or sequence call."),
                    leak_guard("A number cannot be looped over item by item. If you want to loop N times, use 'range(N)'."),
                    leak_guard("Wrap the number in 'range()' if counting, or make sure the variable is a list.")
                ]
            }
        elif "missing" in msg_str and "required positional argument" in msg_str:
            return {
                "explanation": f"Your code has a Type Error{line_ref}. A function was called without providing all of its required arguments.",
                "hints": [
                    leak_guard("When calling a function, you must pass values for every parameter defined in its header."),
                    leak_guard(f"Look at the function call on line {error_line}."),
                    leak_guard(f"The function definition requires parameters, but the call did not provide them: {error_msg}."),
                    leak_guard("Pass the required arguments inside the parentheses when calling the function.")
                ]
            }
        elif "takes" in msg_str and "positional argument" in msg_str:
            return {
                "explanation": f"Your code has a Type Error{line_ref}. Too many arguments were passed to the function.",
                "hints": [
                    leak_guard("A function can only accept the number of arguments declared in its 'def' header."),
                    leak_guard(f"Check the function call on line {error_line} against the function definition."),
                    leak_guard(f"More values were passed than the function expects: {error_msg}."),
                    leak_guard("Remove the extra arguments from the function call, or update the function definition.")
                ]
            }
        elif "does not support item assignment" in msg_str:
            return {
                "explanation": f"Your code has a Type Error{line_ref}. You tried to modify an item in an immutable type (like a tuple or string).",
                "hints": [
                    leak_guard("Strings and tuples in Python are immutable; once created, their individual characters/elements cannot be changed in-place."),
                    leak_guard(f"Look at line {error_line}: check where index assignment 'var[i] = ...' is attempted."),
                    leak_guard("You cannot assign to string indices (e.g. s[0] = 'a') or tuple elements. Use lists if you need to mutate elements."),
                    leak_guard("Convert the data to a list first, or construct a new string using slicing and concatenation.")
                ]
            }
        return {
            "explanation": f"Your code has a Type Error{line_ref}: {error_msg or 'incompatible data types'}.",
            "hints": [
                leak_guard("In Python, each data type has specific operations and methods it supports."),
                leak_guard(f"Inspect the types of the variables used on line {error_line}."),
                leak_guard("Make sure you are not combining mismatched types (like text with numbers) or using methods unsupported by that type."),
                leak_guard("Convert values using functions like int() or str(), or check variable types before operating on them.")
            ]
        }

    # =========================================================================
    # 4. NAME & UNBOUND LOCAL ERRORS
    # =========================================================================
    if "unboundlocalerror" in combined_err:
        return {
            "explanation": f"Your code has an UnboundLocalError{line_ref}. A local variable was referenced before it was assigned a value.",
            "hints": [
                leak_guard("If a variable is assigned anywhere inside a function, Python treats it as a local variable for the entire function."),
                leak_guard(f"Look at line {error_line}: find which variable is being read."),
                leak_guard("You are trying to read this variable before its assignment statement has executed inside the function."),
                leak_guard("Initialize or assign the variable before reading it, or pass it as an argument.")
            ]
        }
    if "nameerror" in combined_err:
        var_match = re.search(r"name '(\w+)' is not defined", msg_str)
        var_name = var_match.group(1) if var_match else "the variable"
        return {
            "explanation": f"Your code has a NameError{line_ref}. '{var_name}' has not been defined or created yet.",
            "hints": [
                leak_guard("Python executes code from top to bottom; a variable or function must be created before you can use it."),
                leak_guard(f"Check the exact spelling and capitalization of '{var_name}' on line {error_line}."),
                leak_guard(f"Look for typos, capitalization differences (Python is case-sensitive), or check if '{var_name}' was defined inside an if-block that did not run."),
                leak_guard(f"Define and assign '{var_name}' before this line runs, or correct any spelling mistakes.")
            ]
        }

    # =========================================================================
    # 5. ATTRIBUTE ERRORS
    # =========================================================================
    if "attributeerror" in combined_err:
        if "'list' object has no attribute 'add'" in msg_str or ("'list'" in msg_str and "add" in line_text):
            return {
                "explanation": f"Your code has an AttributeError{line_ref}. Python lists do not have an '.add()' method.",
                "hints": [
                    leak_guard("Different data structures in Python have different method names for inserting elements."),
                    leak_guard(f"Look at the method call on line {error_line}."),
                    leak_guard("In Python, lists use '.append(item)' to add elements to the end. '.add()' is used for sets, not lists."),
                    leak_guard("Change '.add(...)' to '.append(...)'.")
                ]
            }
        elif "'list' object has no attribute 'push'" in msg_str or ("'list'" in msg_str and "push" in line_text):
            return {
                "explanation": f"Your code has an AttributeError{line_ref}. Python lists do not have a '.push()' method.",
                "hints": [
                    leak_guard("In Python, the list method to append an element is '.append()', not '.push()' like in JavaScript."),
                    leak_guard(f"Look at line {error_line}: check the method called on the list."),
                    leak_guard("To add an item to the end of a list in Python, call '.append(item)'."),
                    leak_guard("Replace '.push(...)' with '.append(...)'.")
                ]
            }
        elif "'str' object has no attribute 'append'" in msg_str:
            return {
                "explanation": f"Your code has an AttributeError{line_ref}. Python strings do not have an '.append()' method.",
                "hints": [
                    leak_guard("Strings are immutable in Python; you cannot append to them like a list."),
                    leak_guard(f"Look at line {error_line} where '.append()' is called on a string."),
                    leak_guard("To add text to an existing string, use '+=' or string concatenation (e.g. text += more_text)."),
                    leak_guard("Use '+=' instead of '.append()' to add text to a string.")
                ]
            }
        elif "'nonetype' object has no attribute" in msg_str:
            return {
                "explanation": f"Your code has an AttributeError{line_ref}. You tried to call a method on 'None'.",
                "hints": [
                    leak_guard("'None' has no attributes or methods."),
                    leak_guard(f"Look at the object before the '.' on line {error_line}."),
                    leak_guard("That variable evaluated to 'None' instead of the expected object. Check if a preceding function forgot its 'return' statement."),
                    leak_guard("Ensure the variable holds a valid object, or check 'if var is not None:' before calling methods.")
                ]
            }
        return {
            "explanation": f"Your code has an AttributeError{line_ref}: {error_msg or 'attribute does not exist'}.",
            "hints": [
                leak_guard("Each Python data type has a specific set of available methods and attributes."),
                leak_guard(f"Check the method or attribute being accessed on line {error_line}."),
                leak_guard(f"The object's type does not support this attribute: {error_msg}."),
                leak_guard("Verify the type of the object and consult Python's built-in methods for that type.")
            ]
        }

    # =========================================================================
    # 6. INDEX ERRORS
    # =========================================================================
    if "indexerror" in combined_err or "range" in combined_err:
        return {
            "explanation": f"Your code has an IndexError{line_ref}. It tried to access an item at an index that does not exist in the list or string.",
            "hints": [
                leak_guard("Python sequences start at index 0 and end at index len - 1. For example, a list of length 3 has valid indices 0, 1, and 2."),
                leak_guard(f"Check which list or string is being indexed on line {error_line}."),
                leak_guard("Your index number reached or exceeded the length of the list, or the list was completely empty (length 0)."),
                leak_guard("Ensure your loop stops before reaching 'len(items)', or check 'if len(items) > index:' before accessing.")
            ]
        }

    # =========================================================================
    # 7. KEY ERRORS
    # =========================================================================
    if "keyerror" in combined_err:
        key_match = re.search(r"keyerror:\s*(.+)", msg_str)
        key_name = key_match.group(1) if key_match else "the requested key"
        return {
            "explanation": f"Your code has a KeyError{line_ref}. The dictionary does not contain {key_name}.",
            "hints": [
                leak_guard("Dictionaries only store values for keys that have been explicitly added."),
                leak_guard(f"Check the dictionary lookup on line {error_line}."),
                leak_guard(f"Directly accessing 'dict[key]' when the key is missing triggers a KeyError: {key_name}."),
                leak_guard("Use 'if key in my_dict:' to check beforehand, or use 'my_dict.get(key, default)' to provide a fallback value.")
            ]
        }

    # =========================================================================
    # 8. VALUE ERRORS
    # =========================================================================
    if "valueerror" in combined_err:
        if "invalid literal for int()" in msg_str:
            return {
                "explanation": f"Your code has a ValueError{line_ref}. You tried to convert a string that contains non-digit characters into an integer with int().",
                "hints": [
                    leak_guard("The 'int()' function can only convert strings containing digits (like '42'), not text, letters, or empty strings."),
                    leak_guard(f"Look at the argument passed to 'int()' on line {error_line}."),
                    leak_guard(f"The input string could not be parsed as a number: {error_msg}."),
                    leak_guard("Clean or validate the string (e.g. 'if text.isdigit():') before converting, or use try/except.")
                ]
            }
        elif "not enough values to unpack" in msg_str or "too many values to unpack" in msg_str:
            return {
                "explanation": f"Your code has a ValueError{line_ref}. The number of variables being unpacked does not match the items in the sequence.",
                "hints": [
                    leak_guard("When unpacking (like 'a, b = items'), the number of variables on the left must exactly equal the number of elements on the right."),
                    leak_guard(f"Check the assignment on line {error_line}."),
                    leak_guard(f"There is a quantity mismatch between variables and values: {error_msg}."),
                    leak_guard("Adjust the variables on the left to match the length of the sequence, or index items individually.")
                ]
            }
        return {
            "explanation": f"Your code has a ValueError{line_ref}: {error_msg or 'invalid value supplied'}.",
            "hints": [
                leak_guard("A function received an argument that has the right type, but an inappropriate value."),
                leak_guard(f"Inspect the values passed to functions on line {error_line}."),
                leak_guard(f"The operation failed because: {error_msg}."),
                leak_guard("Validate the input values before passing them into the function.")
            ]
        }

    # =========================================================================
    # 9. ZERO DIVISION ERRORS
    # =========================================================================
    if "zerodivision" in combined_err:
        return {
            "explanation": f"Your code tried to divide by zero{line_ref}. In mathematics and Python, dividing by zero is undefined.",
            "hints": [
                leak_guard("A number cannot be divided or modulo'd by zero."),
                leak_guard(f"Look at line {error_line}: find where '/', '//', or '%' is used."),
                leak_guard("The denominator evaluated to 0. This frequently happens when dividing by 'len(items)' when the list is empty."),
                leak_guard("Add a check before the division (e.g. 'if count != 0:') to handle the empty or zero case safely.")
            ]
        }

    # =========================================================================
    # 10. TIMEOUT & INFINITE LOOPS
    # =========================================================================
    if "timeout" in combined_err:
        return {
            "explanation": "Your code ran for too long (over 2.0 seconds). This almost always indicates an infinite loop in a 'while' or 'for' loop.",
            "hints": [
                leak_guard("Every loop must have a condition that eventually changes and becomes false so the loop can terminate."),
                leak_guard("Check all 'while' and 'for' loops in your code."),
                leak_guard("Ensure that the loop counter or condition variable is updated on every iteration inside the loop body."),
                leak_guard("Trace your loop variables on paper to confirm the condition reaches its stopping point.")
            ]
        }

    # =========================================================================
    # 11. OUTPUT LIMIT
    # =========================================================================
    if "outputlimit" in combined_err:
        return {
            "explanation": "Your code printed too much text to the terminal (exceeded 4KB limit). This usually happens when print() is inside an infinite loop.",
            "hints": [
                leak_guard("Programs should only output what is needed and avoid printing thousands of lines."),
                leak_guard("Check if you have a 'print()' call inside a loop that runs too many times."),
                leak_guard("Ensure the loop terminates promptly, or remove unnecessary debug print statements."),
                leak_guard("Only print the final answer or summary result.")
            ]
        }

    # Default fallback
    return {
        "explanation": f"Your code encountered {error_type or 'a Python error'}{line_ref} ({error_msg or 'exception raised'}).",
        "hints": [
            leak_guard("An unhandled exception stopped your program from finishing."),
            leak_guard(f"Inspect the operations on line {error_line or 'where the error occurred'}."),
            leak_guard("Check the values and types of variables right before this line executes."),
            leak_guard("Add defensive checks (like checking for empty inputs or None) to handle edge cases safely.")
        ]
    }

