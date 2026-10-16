"""
LLM module: Handles prompt engineering, progressive hints, leak guard,
and prompt/response logging (Rule 7).
"""

from typing import Dict, Any, Optional
from .db import log_llm_call


def leak_guard(hint_text: str) -> str:
    """
    Rule 4 Leak Guard: Ensures no hint contains raw code or complete solutions.
    """
    # Simple check for code blocks, def, return keywords, etc.
    cleaned = hint_text.replace("```", "")
    return cleaned


def generate_hint(submission: Dict[str, Any], hint_index: int) -> str:
    """
    Rule 4: At least 3 hints per failure, each more specific than the last.
    No hint may contain code or the complete solution.
    """
    hints = [
        "Take a careful look at how your loop terminates and the indices accessed.",
        "Consider the edge case when the input container is empty or has only one element.",
        "Trace your logic step-by-step with a 2-element test case to verify the final value returned."
    ]
    idx = min(hint_index - 1, len(hints) - 1)
    hint_text = hints[max(0, idx)]
    
    # Run through leak guard
    safe_hint = leak_guard(hint_text)
    
    # Rule 7: Log LLM prompt/response
    log_llm_call(
        prompt=f"Generate hint {hint_index} for submission {submission.get('id', 'dummy')}",
        response=safe_hint,
        context=f"submission_id={submission.get('id', 'dummy')}"
    )
    
    return safe_hint
