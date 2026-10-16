import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import io
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db import init_db

client = TestClient(app)


def setup_module():
    init_db()


def test_auth_registration_and_login():
    import uuid
    uid = uuid.uuid4().hex[:8]
    test_email = f"pravin_{uid}@example.com"

    # 1. Register a new user
    reg_payload = {
        "name": "Pravin Shinde",
        "email": test_email,
        "password": "secretpassword123"
    }
    res = client.post("/api/auth/register", json=reg_payload)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["success"] is True
    assert data["user"]["email"] == test_email
    assert data["user"]["name"] == "Pravin Shinde"

    # 2. Duplicate registration should fail
    dup_res = client.post("/api/auth/register", json=reg_payload)
    assert dup_res.status_code == 400
    assert "already exists" in dup_res.json()["detail"]

    # 3. Login with correct credentials
    login_res = client.post("/api/auth/login", json={
        "email": test_email,
        "password": "secretpassword123"
    })
    assert login_res.status_code == 200
    assert login_res.json()["success"] is True
    assert login_res.json()["user"]["name"] == "Pravin Shinde"

    # 4. Login with incorrect password
    bad_login = client.post("/api/auth/login", json={
        "email": test_email,
        "password": "wrongpassword"
    })
    assert bad_login.status_code == 401


def test_upload_document_extension_restrictions():
    # Attempting to upload unsupported extensions like .docx or .csv should be rejected
    res = client.post(
        "/api/upload-document",
        files={"file": ("report.docx", io.BytesIO(b"dummy binary content"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    )
    assert res.status_code == 400
    assert "Only .pdf, .py, and .txt files are allowed" in res.json()["detail"]


def test_agentic_verifier_rejects_readme_without_python():
    readme_text = b"""# Project README
This is a web application documentation file.
It describes features, installation steps, and roadmap.
No code is here!
Just plain documentation and project notes.
"""
    res = client.post(
        "/api/upload-document",
        files={"file": ("README.txt", io.BytesIO(readme_text), "text/plain")}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["is_python"] is False
    assert data["success"] is False
    assert "We need Python code to analyze! The uploaded document does not contain any Python code" in data["message"]


def test_agentic_verifier_accepts_py_file():
    py_code = b"""def add_numbers(a, b):
    return a + b

print(add_numbers(3, 4))
"""
    res = client.post(
        "/api/upload-document",
        files={"file": ("solution.py", io.BytesIO(py_code), "text/x-python")}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["is_python"] is True
    assert data["success"] is True
    assert "def add_numbers(a, b):" in data["code"]


def test_analyze_custom_rejects_non_python_text():
    # Directly analyzing non-python text must reject early with the friendly message
    res = client.post("/api/analyze-custom", json={
        "code": "Welcome to my documentation. This file has no programming logic whatsoever.",
        "learner_id": "pravin_test@example.com"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is False
    assert data["outcome"] == "not_python"
    assert "We need Python code to analyze! The uploaded document does not contain any Python code" in data["explanation"]


def test_user_interactions_tracked_on_dashboard():
    import uuid
    user_email = f"pravin_tracker_{uuid.uuid4().hex[:8]}@example.com"
    client.post("/api/auth/register", json={
        "name": "Pravin Tracker",
        "email": user_email,
        "password": "password123"
    })

    # Submit a failing solution
    client.post("/api/submit", json={
        "learner_id": user_email,
        "challenge_id": "count-passes",
        "code": "def count_passes(scores):\n    return -1\n"
    })

    # Submit a passing solution
    client.post("/api/submit", json={
        "learner_id": user_email,
        "challenge_id": "count-passes",
        "code": "def count_passes(scores, threshold=40):\n    return sum(1 for s in scores if s >= threshold)\n"
    })

    # Fetch learner profile
    prof_res = client.get(f"/api/learner/{user_email}")
    assert prof_res.status_code == 200
    prof = prof_res.json()

    assert prof["learner_id"] == user_email
    assert prof["challenges_attempted"] >= 1
    assert prof["challenges_solved"] >= 1
    assert len(prof.get("recurring_mistakes", [])) >= 0
