"""
Tagger module: Detects beginner mistake tags from execution patterns and code analysis.
Tags include: off_by_one, unhandled_short_input, print_not_return, boundary_comparison, mutates_input.
"""

from typing import List, Dict, Any

SUPPORTED_TAGS = [
    "off_by_one",
    "unhandled_short_input",
    "print_not_return",
    "boundary_comparison",
    "mutates_input"
]


def detect_mistakes(code: str, test_results: Dict[str, Any], challenge: Dict[str, Any]) -> List[str]:
    """Analyze code and test failures to tag mistakes."""
    # Stage 1 dummy/stub: return empty list
    return []
