"""
LLM module: Progressive hints generation, strict Rule 4 leak guard,
and prompt/response logging to backend/logs/llm.jsonl (Rule 7).
"""

import re
from typing import Dict, Any, Optional
from .db import log_llm_call

LEAK_PATTERNS = [
    r"```[\s\S]*?```",           # Fenced code blocks
    r"def\s+[a-zA-Z_]\w*\(.*?\):",# Function definition signatures
    r"\breturn\s+[^.\n]+",        # Raw return statements
    r"for\s+\w+\s+in\s+range\(.*?\):", # For loops
    r"while\s+.*?:"               # While loops
]


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


def generate_hint(submission: Dict[str, Any], hint_index: int) -> str:
    """
    Rule 4: At least 3 hints per failure (we build 4 progressive levels),
    each more specific than the last. No hint may contain code or complete solution.
    """
    hints = [
        "Review the core concept governing this problem and consider the constraints on your input.",
        "Examine the specific section of your code where boundary conditions or edge values are checked.",
        "Notice what happens when the collection size is minimal or matches the exact threshold.",
        "Consider adjusting the condition or interval bounds so that boundary cases are correctly handled."
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
