"""
Explain module: Generates plain-language explanations for beginner failures.
Follows Rule 2: Never leaks hidden test values/outputs. May name the KIND of input.
"""

from typing import Dict, Any, List


def explain_failure(test_results: Dict[str, Any], mistake_tags: List[str], challenge: Dict[str, Any]) -> str:
    """Generate an accessible explanation of why tests did not pass."""
    if test_results.get("all_passed", True):
        return "All tests passed! Great job."
    return "Some tests did not pass. Take a close look at how boundaries and inputs are handled."
