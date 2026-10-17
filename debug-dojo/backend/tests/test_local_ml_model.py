"""
Unit tests verifying the local offline Machine Learning model:
- Verifies dojo_ml_model.joblib exists and loads cleanly.
- Tests ML classification accuracy on code snippets and error contexts.
- Validates 0 external API calls and local hint generation across all 5 levels.
"""

import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from app.ml_engine import (
    MODEL_PATH,
    get_trained_model,
    predict_bug_category,
    generate_ml_hint,
    leak_guard
)
from app.llm import USE_EXTERNAL_AI_API, get_gemini_api_key, LOCAL_ML_MODEL_NAME


def test_ml_model_file_exists():
    """Verify that the trained ML model artifact exists on disk."""
    assert os.path.exists(MODEL_PATH), f"Model file missing at: {MODEL_PATH}"
    size_bytes = os.path.getsize(MODEL_PATH)
    assert size_bytes > 1000, f"Model file suspiciously small ({size_bytes} bytes)"


def test_ml_model_loads_and_has_metadata():
    """Verify the serialized joblib payload has expected pipeline and metadata."""
    payload = get_trained_model()
    assert payload is not None
    assert "pipeline" in payload
    assert "classes" in payload
    assert "invariants" in payload
    assert "metadata" in payload
    meta = payload["metadata"]
    assert meta["training_samples"] >= 10
    assert meta["training_accuracy"] >= 0.95


def test_ml_classification_print_not_return():
    """Verify the trained ML model classifies missing return as print_not_return."""
    code = "def add(a, b):\n    print(a + b)"
    err = "function returned None instead of 10"
    tag, conf, inv = predict_bug_category(code, err)
    assert tag == "print_not_return"
    assert inv == "function_return_contract"


def test_ml_classification_zero_division():
    """Verify the trained ML model classifies ZeroDivisionError."""
    code = "def divide_all(total, count):\n    return total / count"
    err = "ZeroDivisionError: division by zero"
    tag, conf, inv = predict_bug_category(code, err)
    assert tag == "zero_division"
    assert inv == "zero_division_guard"


def test_ml_classification_boundary_comparison():
    """Verify the trained ML model classifies boundary comparison errors."""
    code = "def is_passing(marks):\n    return [m for m in marks if m > 40]"
    err = "boundary error: mark of 40 should pass with >="
    tag, conf, inv = predict_bug_category(code, err)
    assert tag == "boundary_comparison"
    assert inv == "inequality_boundary"


def test_ml_hint_generation_all_five_levels():
    """Verify local ML engine generates 5 distinct progressive hints without network."""
    challenge = {"id": "test-ch", "title": "Test Challenge"}
    code = "def solve(items):\n    return items[10]"
    
    seen_hints = []
    for lvl in range(1, 6):
        res = generate_ml_hint(
            challenge=challenge,
            code=code,
            hint_level=lvl,
            error_type="IndexError",
            error_line=2,
            error_msg="list index out of range"
        )
        assert res["hint_level"] == lvl
        assert res["model_used"] == "🧠 Dojo Local ML Model (Trained Offline - Scikit-Learn)"
        assert len(res["hint"]) > 10
        assert res["hint"] not in seen_hints
        seen_hints.append(res["hint"])

    assert len(seen_hints) == 5


def test_external_ai_api_disabled_by_default():
    """Verify no external AI APIs are called when USE_EXTERNAL_AI_API is false."""
    assert USE_EXTERNAL_AI_API is False
    # Even if environment variable or param is passed, key is rejected
    key = get_gemini_api_key("some_key")
    assert key == "", "External API key must be empty when USE_EXTERNAL_AI_API is False"
