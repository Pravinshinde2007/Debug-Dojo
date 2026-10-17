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
    assert "token" in data and len(data["token"]) > 20
    reg_token = data["token"]

    # Verify token with /auth/me
    me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {reg_token}"})
    assert me_res.status_code == 200
    assert me_res.json()["authenticated"] is True
    assert me_res.json()["user"]["email"] == test_email

    # Verify user is genuinely stored in the database
    from app.db import get_user_by_email
    db_user = get_user_by_email(test_email)
    assert db_user is not None
    assert db_user["email"].lower() == test_email.lower()
    assert db_user["name"] == "Pravin Shinde"

    # 2. Duplicate registration should fail (both exact and case-insensitive)
    dup_res = client.post("/api/auth/register", json=reg_payload)
    assert dup_res.status_code == 400
    assert "already exists" in dup_res.json()["detail"]

    dup_case_res = client.post("/api/auth/register", json={
        "name": "Different Name",
        "email": test_email.upper(),
        "password": "anotherpassword"
    })
    assert dup_case_res.status_code == 400
    assert "already exists" in dup_case_res.json()["detail"]

    # 3. Login with correct credentials
    login_res = client.post("/api/auth/login", json={
        "email": test_email,
        "password": "secretpassword123"
    })
    assert login_res.status_code == 200
    login_data = login_res.json()
    assert login_data["success"] is True
    assert login_data["user"]["name"] == "Pravin Shinde"
    assert "token" in login_data and len(login_data["token"]) > 20
    login_token = login_data["token"]

    # 4. Login with incorrect password
    bad_login = client.post("/api/auth/login", json={
        "email": test_email,
        "password": "wrongpassword"
    })
    assert bad_login.status_code == 401

    # 5. Logout revokes token
    logout_res = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {login_token}"})
    assert logout_res.status_code == 200
    assert logout_res.json()["success"] is True

    # 6. Revoked token fails authentication
    after_logout_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {login_token}"})
    assert after_logout_res.status_code == 200
    assert after_logout_res.json()["authenticated"] is False


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
    reg = client.post("/api/auth/register", json={
        "name": "Pravin Tracker",
        "email": user_email,
        "password": "password123"
    })
    token = reg.json()["token"]

    # Submit a failing solution with Bearer token
    client.post("/api/submit", json={
        "learner_id": user_email,
        "challenge_id": "count-passes",
        "code": "def count_passes(scores):\n    return -1\n"
    }, headers={"Authorization": f"Bearer {token}"})

    # Submit a passing solution
    client.post("/api/submit", json={
        "learner_id": user_email,
        "challenge_id": "count-passes",
        "code": "def count_passes(scores, threshold=40):\n    return sum(1 for s in scores if s >= threshold)\n"
    }, headers={"Authorization": f"Bearer {token}"})

    # Execute custom code debugging with Bearer token
    client.post("/api/analyze-custom", json={
        "code": "print('hello from custom debug')",
        "learner_id": user_email
    }, headers={"Authorization": f"Bearer {token}"})

    # Fetch learner profile
    prof_res = client.get(f"/api/learner/{user_email}", headers={"Authorization": f"Bearer {token}"})
    assert prof_res.status_code == 200
    prof = prof_res.json()

    assert prof["learner_id"] == user_email or prof["user_email"] == user_email
    assert prof["challenges_attempted"] >= 1
    assert prof["challenges_solved"] >= 1
    assert prof["custom_debug_count"] >= 1
    assert prof["total_submissions"] >= 3
    assert len(prof.get("history", [])) >= 3
    # Verify history items are real database entries
    assert any(h["challenge_id"] == "custom-code" for h in prof["history"])
    assert any(h["challenge_id"] == "count-passes" for h in prof["history"])
