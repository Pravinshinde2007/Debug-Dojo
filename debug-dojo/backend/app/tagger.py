"""
Tagger module: Multi-signal deterministic mistake detector.
Detects beginner mistake tags from execution patterns, AST analysis,
stdout vs return values, and argument mutation tracking.

Categories:
1. off_by_one
2. unhandled_short_input
3. print_not_return
4. boundary_comparison
5. mutates_input
"""

import ast
from typing import List, Dict, Any, Optional

SUPPORTED_TAGS = [
    "off_by_one",
    "unhandled_short_input",
    "print_not_return",
    "boundary_comparison",
    "mutates_input"
]


class CodeASTAnalyzer(ast.NodeVisitor):
    def __init__(self):
        self.has_print = False
        self.has_return = False
        self.return_values = []
        self.comparisons = []
        self.ranges = []
        self.slice_indices = []
        self.mutating_methods = []

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name):
            if node.func.id == "print":
                self.has_print = True
            elif node.func.id == "range":
                args = []
                for a in node.args:
                    if isinstance(a, ast.Constant):
                        args.append(a.value)
                    elif isinstance(a, ast.Name):
                        args.append(a.id)
                    else:
                        args.append("expr")
                self.ranges.append(args)
        elif isinstance(node.func, ast.Attribute):
            if node.func.attr in ("pop", "remove", "clear", "extend", "append", "insert"):
                self.mutating_methods.append(node.func.attr)
        self.generic_visit(node)

    def visit_Return(self, node):
        self.has_return = True
        if node.value is not None:
            self.return_values.append(node.value)
        self.generic_visit(node)

    def visit_Compare(self, node):
        for op in node.ops:
            self.comparisons.append(type(op).__name__)
        self.generic_visit(node)

    def visit_Subscript(self, node):
        if isinstance(node.slice, ast.Slice):
            self.slice_indices.append((node.slice.lower, node.slice.upper, node.slice.step))
        self.generic_visit(node)


def analyze_ast(code: str) -> Optional[CodeASTAnalyzer]:
    try:
        tree = ast.parse(code)
        analyzer = CodeASTAnalyzer()
        analyzer.visit(tree)
        return analyzer
    except Exception:
        return None


def detect_mistakes(code: str, test_run_data: Dict[str, Any], challenge: Dict[str, Any]) -> List[str]:
    """
    Deterministically detects mistake tags by analyzing test outcomes,
    input kinds, return values, stdout, mutations, and code AST.
    """
    tags = set()
    detailed_tests = test_run_data.get("_detailed_data", [])
    ast_info = analyze_ast(code)

    has_pass = any(t["outcome"] == "passed" for t in detailed_tests)
    has_fail = any(t["outcome"] != "passed" for t in detailed_tests)

    # 1. Detection of 'mutates_input'
    for t in detailed_tests:
        if t.get("mutated_input"):
            tags.add("mutates_input")
            break

    # 2. Detection of 'print_not_return'
    # Condition: function returned None for a test expecting non-None, while stdout is non-empty
    print_flagged = False
    for t in detailed_tests:
        if t["outcome"] != "passed":
            got_val = t.get("got")
            expected_val = t.get("expected")
            stdout_str = t.get("stdout", "").strip()

            if got_val is None and expected_val is not None and stdout_str:
                # If output contains representation of expected value or non-empty printed output
                tags.add("print_not_return")
                print_flagged = True
                break

    if not print_flagged and ast_info:
        if ast_info.has_print and (not ast_info.has_return or len(ast_info.return_values) == 0):
            tags.add("print_not_return")

    # 3. Detection of 'unhandled_short_input'
    # Condition: Normal cases pass, but empty/short/boundary input crashes or produces wrong output
    short_input_failed = False
    for t in detailed_tests:
        kind = (t.get("kind") or "").lower()
        args = t.get("args") or []
        
        # Check if test targets empty list, zero k, or sub-boundary
        is_short_or_empty = (
            "empty" in kind or
            "short" in kind or
            "singleton" in kind or
            "smaller than" in kind or
            "larger than the list" in kind or
            any(isinstance(a, (list, str)) and len(a) == 0 for a in args) or
            any(isinstance(a, (int, float)) and a <= 0 for a in args)
        )

        if is_short_or_empty and t["outcome"] != "passed":
            # If normal tests pass, this specifically isolates unhandled short input
            tags.add("unhandled_short_input")
            short_input_failed = True
            break

    # 4. Detection of 'boundary_comparison'
    # Condition: Equality threshold mismatch (e.g. mark >= 40 vs mark > 40)
    for t in detailed_tests:
        kind = (t.get("kind") or "").lower()
        if "boundary" in kind or "threshold" in kind or "equal" in kind or "exact" in kind:
            if t["outcome"] != "passed":
                tags.add("boundary_comparison")
                break

    if "boundary_comparison" not in tags and ast_info:
        # Check AST comparisons in threshold challenges
        challenge_id = challenge.get("id", "")
        if "pass" in challenge_id or "clamp" in challenge_id:
            if "Gt" in ast_info.comparisons and "GtE" not in ast_info.comparisons:
                tags.add("boundary_comparison")
            elif "Lt" in ast_info.comparisons and "LtE" not in ast_info.comparisons:
                tags.add("boundary_comparison")

    # 5. Detection of 'off_by_one'
    for t in detailed_tests:
        if t["outcome"] != "passed":
            got = t.get("got")
            expected = t.get("expected")

            # Check length difference of 1 on lists/collections
            if isinstance(got, (list, tuple, str)) and isinstance(expected, (list, tuple, str)):
                if abs(len(got) - len(expected)) == 1:
                    tags.add("off_by_one")
                    break
                # Check starting with 0 when positive numbers expected (e.g. range(n) vs range(1, n+1))
                if len(got) > 0 and len(expected) > 0:
                    if got[0] == 0 and expected[0] != 0:
                        tags.add("off_by_one")
                        break

            # Numeric difference of 1
            if isinstance(got, (int, float)) and isinstance(expected, (int, float)):
                if abs(got - expected) == 1:
                    tags.add("off_by_one")
                    break

    if "off_by_one" not in tags and ast_info:
        challenge_id = challenge.get("id", "")
        if "square" in challenge_id:
            # Check if range has 1 arg instead of 2 args
            for r in ast_info.ranges:
                if len(r) == 1:
                    tags.add("off_by_one")
                    break

    # Return sorted list of valid tags
    return [t for t in SUPPORTED_TAGS if t in tags]
