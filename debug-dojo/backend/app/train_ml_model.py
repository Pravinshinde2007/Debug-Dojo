"""
Training script for Debug Dojo's Local Offline ML Model.
Trains a scikit-learn NLP classification pipeline on Python learner code,
tracebacks, and mistake patterns. Serializes the trained model to models/dojo_ml_model.joblib.
Zero external AI APIs are required.
"""

import os
import joblib
import numpy as np
from typing import Dict, Any, List, Tuple
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report, accuracy_score

TRAINING_DATA: List[Dict[str, str]] = [
    # 1. off_by_one
    {
        "code": "def solve(nums):\n    total = 0\n    for i in range(len(nums) - 1):\n        total += nums[i]\n    return total",
        "error": "failing on last element: missed nums[-1]",
        "tag": "off_by_one",
        "invariant": "loop_range_bounds"
    },
    {
        "code": "def first_n(n):\n    res = []\n    for i in range(1, n):\n        res.append(i * i)\n    return res",
        "error": "got n-1 elements instead of n elements",
        "tag": "off_by_one",
        "invariant": "loop_range_bounds"
    },
    {
        "code": "def count_up(n):\n    i = 0\n    while i < n - 1:\n        i += 1\n    return i",
        "error": "stopped 1 short of upper bound",
        "tag": "off_by_one",
        "invariant": "loop_range_bounds"
    },
    {
        "code": "def slice_k(arr, k):\n    return arr[:k-1]",
        "error": "slice excluded boundary element at index k-1",
        "tag": "off_by_one",
        "invariant": "sequence_slice_bounds"
    },
    {
        "code": "def traverse(items):\n    for i in range(0, len(items) + 1):\n        print(items[i])",
        "error": "IndexError: list index out of range at len(items)",
        "tag": "off_by_one",
        "invariant": "loop_range_bounds"
    },

    # 2. unhandled_short_input
    {
        "code": "def middle_three(s):\n    mid = len(s) // 2\n    return s[mid-1:mid+2]",
        "error": "failed on empty string s='' or s='a': string too short",
        "tag": "unhandled_short_input",
        "invariant": "short_input_guard"
    },
    {
        "code": "def head_and_tail(lst):\n    return lst[0] + lst[-1]",
        "error": "IndexError: list index out of range on empty list []",
        "tag": "unhandled_short_input",
        "invariant": "short_input_guard"
    },
    {
        "code": "def last_k_total(marks, k):\n    return sum(marks[-k:])",
        "error": "failed on marks=[] empty list or k=0",
        "tag": "unhandled_short_input",
        "invariant": "short_input_guard"
    },
    {
        "code": "def average(nums):\n    return sum(nums) / len(nums)",
        "error": "ZeroDivisionError: division by zero on empty list nums=[]",
        "tag": "unhandled_short_input",
        "invariant": "short_input_guard"
    },
    {
        "code": "def get_second(arr):\n    return arr[1]",
        "error": "IndexError: list index out of range on single item list [42]",
        "tag": "unhandled_short_input",
        "invariant": "short_input_guard"
    },

    # 3. print_not_return
    {
        "code": "def calculate_sum(a, b):\n    print(a + b)",
        "error": "function returned None instead of expected number",
        "tag": "print_not_return",
        "invariant": "function_return_contract"
    },
    {
        "code": "def count_passes(marks):\n    c = sum(1 for m in marks if m >= 40)\n    print(f'Passes: {c}')",
        "error": "function printed output but returned None",
        "tag": "print_not_return",
        "invariant": "function_return_contract"
    },
    {
        "code": "def is_valid(s):\n    if len(s) > 5:\n        print(True)\n    else:\n        print(False)",
        "error": "returned None got None expected boolean True",
        "tag": "print_not_return",
        "invariant": "function_return_contract"
    },
    {
        "code": "def solve(items):\n    res = [x * 2 for x in items]\n    print(res)",
        "error": "missing return statement, printed list to stdout",
        "tag": "print_not_return",
        "invariant": "function_return_contract"
    },

    # 4. boundary_comparison
    {
        "code": "def count_passes(marks):\n    return sum(1 for m in marks if m > 40)",
        "error": "used strictly greater than > instead of >= passing mark 40 failed mark=40",
        "tag": "boundary_comparison",
        "invariant": "inequality_boundary"
    },
    {
        "code": "def is_adult(age):\n    return age > 18",
        "error": "expected True for age=18 got False boundary missed",
        "tag": "boundary_comparison",
        "invariant": "inequality_boundary"
    },
    {
        "code": "def check_capacity(count, limit):\n    if count < limit:\n        return 'OK'\n    return 'FULL'",
        "error": "at count==limit expected OK got FULL used < instead of <=",
        "tag": "boundary_comparison",
        "invariant": "inequality_boundary"
    },
    {
        "code": "def validate_score(score):\n    return 0 < score < 100",
        "error": "failed for score=0 and score=100 bounds should be inclusive <=",
        "tag": "boundary_comparison",
        "invariant": "inequality_boundary"
    },

    # 5. mutates_input
    {
        "code": "def sort_and_filter(items):\n    items.sort()\n    return items[:5]",
        "error": "input list was mutated in-place by sort() original list modified",
        "tag": "mutates_input",
        "invariant": "input_immutability"
    },
    {
        "code": "def remove_evens(nums):\n    for x in list(nums):\n        if x % 2 == 0:\n            nums.remove(x)\n    return nums",
        "error": "mutated caller argument in place using remove()",
        "tag": "mutates_input",
        "invariant": "input_immutability"
    },
    {
        "code": "def append_total(lst):\n    lst.append(sum(lst))\n    return lst",
        "error": "original list modified with append() caller data corrupted",
        "tag": "mutates_input",
        "invariant": "input_immutability"
    },
    {
        "code": "def clear_negatives(d):\n    d.pop('negative', None)\n    return d",
        "error": "mutated input dictionary in-place",
        "tag": "mutates_input",
        "invariant": "input_immutability"
    },

    # 6. zero_division
    {
        "code": "def divide_all(total, count):\n    return total / count",
        "error": "ZeroDivisionError: division by zero",
        "tag": "zero_division",
        "invariant": "zero_division_guard"
    },
    {
        "code": "def compute_ratio(a, b):\n    res = a % b\n    return res",
        "error": "ZeroDivisionError: integer division or modulo by zero",
        "tag": "zero_division",
        "invariant": "zero_division_guard"
    },
    {
        "code": "def calc_mean(nums):\n    s = sum(nums)\n    l = len(nums)\n    return s // l",
        "error": "ZeroDivisionError: integer division by zero",
        "tag": "zero_division",
        "invariant": "zero_division_guard"
    },

    # 7. index_error
    {
        "code": "def get_first(items):\n    return items[0]",
        "error": "IndexError: list index out of range",
        "tag": "index_error",
        "invariant": "index_bounds_guard"
    },
    {
        "code": "def get_last(items):\n    return items[len(items)]",
        "error": "IndexError: list index out of range off by one upper index",
        "tag": "index_error",
        "invariant": "index_bounds_guard"
    },
    {
        "code": "def matrix_cell(grid, r, c):\n    return grid[r][c]",
        "error": "IndexError: list index out of range row or column exceeded",
        "tag": "index_error",
        "invariant": "index_bounds_guard"
    },

    # 8. type_error
    {
        "code": "def add_text(name, num):\n    return 'User ' + num",
        "error": "TypeError: can only concatenate str (not 'int') to str",
        "tag": "type_error",
        "invariant": "type_compatibility"
    },
    {
        "code": "def find_len(val):\n    return len(val)",
        "error": "TypeError: object of type 'int' has no len()",
        "tag": "type_error",
        "invariant": "type_compatibility"
    },
    {
        "code": "def iterate_val(val):\n    for x in val:\n        pass",
        "error": "TypeError: 'int' object is not iterable",
        "tag": "type_error",
        "invariant": "type_compatibility"
    },

    # 9. key_error
    {
        "code": "def get_setting(config, k):\n    return config[k]",
        "error": "KeyError: 'theme' missing key from dictionary lookup",
        "tag": "key_error",
        "invariant": "dict_key_membership"
    },
    {
        "code": "def tally(words):\n    counts = {}\n    for w in words:\n        counts[w] += 1\n    return counts",
        "error": "KeyError: key not found during direct lookup before initialization",
        "tag": "key_error",
        "invariant": "dict_key_membership"
    },

    # 10. timeout_tle
    {
        "code": "def find_cycle(nums):\n    while True:\n        pass\n    return nums",
        "error": "Timeout: Execution timed out after 2.0s infinite while loop",
        "tag": "timeout_tle",
        "invariant": "loop_termination"
    },
    {
        "code": "def count_pairs(nums):\n    c = 0\n    for i in range(len(nums)):\n        for j in range(len(nums)):\n            if nums[i] == nums[j]: c += 1\n    return c",
        "error": "Timeout: Execution timed out O(N^2) time limit exceeded on large test",
        "tag": "timeout_tle",
        "invariant": "loop_termination"
    }
]


def extract_features(sample: Dict[str, str]) -> str:
    """Concatenates code and error text into feature representation."""
    code = sample.get("code", "")
    err = sample.get("error", "")
    return f"CODE_START\n{code}\nCODE_END\nERROR_CONTEXT: {err}"


def train_and_serialize_model():
    """Trains scikit-learn TF-IDF + LogisticRegression model on bug patterns."""
    X = [extract_features(sample) for sample in TRAINING_DATA]
    y = [sample["tag"] for sample in TRAINING_DATA]
    invariants = {sample["tag"]: sample["invariant"] for sample in TRAINING_DATA}

    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(
            ngram_range=(1, 2),
            token_pattern=r"(?u)\b\w+\b|[><=]+|\[\]|\{\}",
            max_features=2000
        )),
        ("clf", LogisticRegression(
            C=3.0,
            max_iter=500,
            random_state=42
        ))
    ])

    pipeline.fit(X, y)
    preds = pipeline.predict(X)
    acc = accuracy_score(y, preds)
    print(f"Training Complete. Training Accuracy: {acc * 100:.2f}%")

    model_dir = os.path.join(os.path.dirname(__file__), "models")
    os.makedirs(model_dir, exist_ok=True)
    model_path = os.path.join(model_dir, "dojo_ml_model.joblib")

    payload = {
        "pipeline": pipeline,
        "classes": list(pipeline.classes_),
        "invariants": invariants,
        "metadata": {
            "model_name": "🧠 Dojo Local ML Model (Trained Offline - Scikit-Learn)",
            "version": "1.0.0",
            "training_samples": len(X),
            "training_accuracy": acc
        }
    }

    joblib.dump(payload, model_path)
    print(f"Model saved successfully to: {model_path}")
    return model_path


if __name__ == "__main__":
    train_and_serialize_model()
