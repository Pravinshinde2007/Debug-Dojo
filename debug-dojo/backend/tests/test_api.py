import sys
from pathlib import Path

# Add backend directory to path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db import get_db_connection

client = TestClient(app)


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_submit_endpoint_shape():
    payload = {
        "learner_id": "test_learner_01",
        "challenge_id": "challenge_1",
        "code": "def sum_elements(nums): return sum(nums)"
    }
    response = client.post("/api/submit", json=payload)
    assert response.status_code == 200
    data = response.json()
    
    # Check exact API keys required by spec
    assert "submission_id" in data
    assert data["learner_id"] == "test_learner_01"
    assert data["challenge_id"] == "challenge_1"
    assert "visible" in data
    assert isinstance(data["visible"], list)
    assert len(data["visible"]) > 0
    assert all(k in data["visible"][0] for k in ("test", "call", "expected", "got", "outcome"))
    assert data["visible"][0]["outcome"] in ("passed", "wrong_output", "runtime_error", "timeout")
    
    assert "hidden" in data
    assert isinstance(data["hidden"], list)
    assert len(data["hidden"]) > 0
    assert all(k in data["hidden"][0] for k in ("test", "outcome"))
    # Verify hidden tests do NOT leak call, expected, or got
    assert "call" not in data["hidden"][0]
    assert "expected" not in data["hidden"][0]
    assert "got" not in data["hidden"][0]
    
    assert "mistake_tags" in data
    assert isinstance(data["mistake_tags"], list)
    assert "explanation" in data


def test_hint_endpoint_shape():
    # Submit first to get submission_id
    sub_res = client.post("/api/submit", json={
        "learner_id": "test_learner_01",
        "challenge_id": "challenge_1",
        "code": "pass"
    })
    submission_id = sub_res.json()["submission_id"]

    hint_res = client.post("/api/hint", json={"submission_id": submission_id})
    assert hint_res.status_code == 200
    hdata = hint_res.json()
    assert "hint" in hdata
    assert isinstance(hdata["hint"], str)
    assert len(hdata["hint"]) > 0


def test_learner_profile_shape():
    response = client.get("/api/learner/test_learner_01")
    assert response.status_code == 200
    ldata = response.json()
    assert "recurring_mistakes" in ldata
    assert isinstance(ldata["recurring_mistakes"], list)
    assert "mastery_per_concept" in ldata
    assert isinstance(ldata["mastery_per_concept"], dict)
    assert "next_challenge" in ldata
    assert "reason" in ldata


def test_sqlite_tables_exist():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row["name"] for row in cursor.fetchall()]
        assert "submissions" in tables
        assert "hints_given" in tables
        assert "learner_events" in tables
        assert "llm_log" in tables


def test_analyze_custom_syntax_error():
    # Buggy code with missing colon
    code = """def calculate_total(a, b)
    return a + b
"""
    res = client.post("/api/analyze-custom", json={"code": code})
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is False
    assert data["outcome"] == "syntax_error"
    assert "SyntaxError" in data["error_type"]
    assert data["error_line"] == 1
    assert "Syntax Error" in data["explanation"]
    assert len(data["hints"]) == 4
    # Rule 4: No code solution leaks in hints!
    for h in data["hints"]:
        assert "def calculate_total" not in h
        assert "return a + b" not in h


def test_analyze_custom_runtime_error():
    # ZeroDivisionError
    code = """def calc_avg(nums):
    total = sum(nums)
    return total / len(nums)

print(calc_avg([]))
"""
    res = client.post("/api/analyze-custom", json={"code": code})
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is False
    assert data["outcome"] == "runtime_error"
    assert "ZeroDivisionError" in (data["error_type"] or data["error_msg"])
    assert "divide by zero" in data["explanation"].lower() or "zero" in data["explanation"].lower()
    assert len(data["hints"]) == 4


def test_analyze_custom_from_document():
    doc = """
# Homework Assignment 3
Please find the bug in this Python snippet:

```python
names = ['Alice', 'Bob']
print(names[5])
```
"""
    res = client.post("/api/analyze-custom", json={"document_text": doc})
    assert res.status_code == 200
    data = res.json()
    assert data["extracted_from_doc"] is True
    assert "names[5]" in data["cleaned_code"]
    assert data["outcome"] == "runtime_error"
    assert "Index" in (data["error_type"] or data["error_msg"])


def test_analyze_custom_clean_run():
    code = """val = 40 + 2
print(f"Computed: {val}")
"""
    res = client.post("/api/analyze-custom", json={"code": code})
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["outcome"] == "passed"
    assert "Computed: 42" in data["stdout"]
