"""
Supabase Database Integration for Debug Dojo
Connects via Supabase PostgREST HTTPS API using httpx.
Works natively in serverless (Vercel) and local dev environments without connection exhaustion or binary driver issues.
"""

import os
import json
import logging
from typing import Optional, Dict, Any, List
import httpx

logger = logging.getLogger("supabase_db")

def get_supabase_url() -> str:
    return (os.environ.get("SUPABASE_URL") or os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or "").rstrip("/")

def get_supabase_key() -> str:
    return (
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or
        os.environ.get("SUPABASE_KEY") or
        os.environ.get("SUPABASE_ANON_KEY") or
        os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY") or
        ""
    ).strip()

def is_supabase_configured() -> bool:
    """Returns True if Supabase URL and key are present in environment."""
    url = get_supabase_url()
    key = get_supabase_key()
    return bool(url and key and "supabase.co" in url)


def _get_headers() -> Dict[str, str]:
    key = get_supabase_key()
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }


def _get_rest_url(table: str) -> str:
    url = get_supabase_url()
    return f"{url}/rest/v1/{table}"



# --- Users ---

def supabase_create_user(user_id: str, name: str, email: str, password_hash: str, salt: str) -> Optional[Dict[str, Any]]:
    if not is_supabase_configured():
        return None
    try:
        payload = {
            "id": user_id,
            "name": name,
            "email": email.strip().lower(),
            "password_hash": password_hash,
            "salt": salt
        }
        with httpx.Client(timeout=8.0) as client:
            res = client.post(_get_rest_url("users"), json=payload, headers=_get_headers())
            if res.is_success:
                rows = res.json()
                return rows[0] if isinstance(rows, list) and rows else payload
            logger.warning(f"Supabase create_user HTTP {res.status_code}: {res.text}")
    except Exception as exc:
        logger.error(f"Supabase create_user error: {exc}")
    return None


def supabase_get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    if not is_supabase_configured():
        return None
    try:
        clean_email = email.strip().lower()
        with httpx.Client(timeout=8.0) as client:
            res = client.get(
                f"{_get_rest_url('users')}?email=eq.{clean_email}&select=*",
                headers=_get_headers()
            )
            if res.is_success:
                rows = res.json()
                if isinstance(rows, list) and len(rows) > 0:
                    return rows[0]
    except Exception as exc:
        logger.error(f"Supabase get_user_by_email error: {exc}")
    return None


def supabase_get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    if not is_supabase_configured():
        return None
    try:
        with httpx.Client(timeout=8.0) as client:
            res = client.get(
                f"{_get_rest_url('users')}?id=eq.{user_id}&select=*",
                headers=_get_headers()
            )
            if res.is_success:
                rows = res.json()
                if isinstance(rows, list) and len(rows) > 0:
                    return rows[0]
    except Exception as exc:
        logger.error(f"Supabase get_user_by_id error: {exc}")
    return None


# --- User Tokens ---

def supabase_save_user_token(user_id: str, token: str, expires_at: str) -> bool:
    if not is_supabase_configured():
        return False
    try:
        payload = {
            "user_id": user_id,
            "token": token,
            "expires_at": expires_at,
            "revoked": 0
        }
        with httpx.Client(timeout=8.0) as client:
            res = client.post(_get_rest_url("user_tokens"), json=payload, headers=_get_headers())
            return res.is_success
    except Exception as exc:
        logger.error(f"Supabase save_user_token error: {exc}")
    return False


def supabase_verify_user_token(token: str) -> Optional[Dict[str, Any]]:
    if not is_supabase_configured():
        return None
    try:
        with httpx.Client(timeout=8.0) as client:
            res = client.get(
                f"{_get_rest_url('user_tokens')}?token=eq.{token}&select=*",
                headers=_get_headers()
            )
            if res.is_success:
                rows = res.json()
                if isinstance(rows, list) and len(rows) > 0:
                    row = rows[0]
                    if row.get("revoked") == 1:
                        return None
                    return supabase_get_user_by_id(row["user_id"])
    except Exception as exc:
        logger.error(f"Supabase verify_user_token error: {exc}")
    return None


def supabase_revoke_user_token(token: str) -> bool:
    if not is_supabase_configured():
        return False
    try:
        with httpx.Client(timeout=8.0) as client:
            res = client.patch(
                f"{_get_rest_url('user_tokens')}?token=eq.{token}",
                json={"revoked": 1},
                headers=_get_headers()
            )
            return res.is_success
    except Exception as exc:
        logger.error(f"Supabase revoke_user_token error: {exc}")
    return False


# --- Sandbox Attempts ---

def supabase_save_sandbox_attempt(
    attempt_id: str,
    user_id: str,
    problem_title: str,
    problem_statement: str,
    problem_spec: Dict[str, Any],
    language: str,
    code: str,
    mode: str,
    passed: bool,
    test_results: Dict[str, Any],
    feedback: Dict[str, Any]
) -> bool:
    if not is_supabase_configured():
        return False
    try:
        payload = {
            "id": attempt_id,
            "user_id": user_id,
            "problem_title": problem_title,
            "problem_statement": problem_statement,
            "problem_spec": json.dumps(problem_spec),
            "language": language,
            "code": code,
            "mode": mode,
            "passed": 1 if passed else 0,
            "test_results": json.dumps(test_results),
            "feedback": json.dumps(feedback)
        }
        with httpx.Client(timeout=8.0) as client:
            res = client.post(_get_rest_url("sandbox_attempts"), json=payload, headers=_get_headers())
            return res.is_success
    except Exception as exc:
        logger.error(f"Supabase save_sandbox_attempt error: {exc}")
    return False


def supabase_get_sandbox_attempts(user_id: str, limit: int = 10) -> Optional[List[Dict[str, Any]]]:
    if not is_supabase_configured():
        return None
    try:
        with httpx.Client(timeout=8.0) as client:
            res = client.get(
                f"{_get_rest_url('sandbox_attempts')}?user_id=eq.{user_id}&order=created_at.desc&limit={limit}&select=*",
                headers=_get_headers()
            )
            if res.is_success:
                rows = res.json()
                result = []
                for r in rows:
                    result.append({
                        "id": r["id"],
                        "user_id": r["user_id"],
                        "problem_title": r["problem_title"],
                        "problem_statement": r.get("problem_statement") or "",
                        "language": r["language"],
                        "code": r["code"],
                        "mode": r["mode"],
                        "passed": bool(r["passed"]),
                        "test_results": json.loads(r["test_results"]) if isinstance(r["test_results"], str) else (r["test_results"] or {}),
                        "feedback": json.loads(r["feedback"]) if isinstance(r["feedback"], str) else (r["feedback"] or {}),
                        "created_at": r["created_at"]
                    })
                return result
    except Exception as exc:
        logger.error(f"Supabase get_sandbox_attempts error: {exc}")
    return None


# --- Submissions & Hints ---

def supabase_save_submission(sub_id: str, learner_id: str, challenge_id: str, code: str, visible: str, hidden: str, tags: str, explanation: str, passed: int) -> bool:
    if not is_supabase_configured():
        return False
    try:
        payload = {
            "id": sub_id,
            "learner_id": learner_id,
            "challenge_id": challenge_id,
            "code": code,
            "visible_results": visible,
            "hidden_results": hidden,
            "mistake_tags": tags,
            "explanation": explanation,
            "passed": passed
        }
        with httpx.Client(timeout=8.0) as client:
            res = client.post(_get_rest_url("submissions"), json=payload, headers=_get_headers())
            return res.is_success
    except Exception as exc:
        logger.error(f"Supabase save_submission error: {exc}")
    return False


def supabase_save_hint(sub_id: str, learner_id: str, hint_index: int, hint_text: str) -> bool:
    if not is_supabase_configured():
        return False
    try:
        payload = {
            "submission_id": sub_id,
            "learner_id": learner_id,
            "hint_index": hint_index,
            "hint_text": hint_text
        }
        with httpx.Client(timeout=8.0) as client:
            res = client.post(_get_rest_url("hints_given"), json=payload, headers=_get_headers())
            return res.is_success
    except Exception as exc:
        logger.error(f"Supabase save_hint error: {exc}")
    return False


def supabase_log_event(learner_id: str, event_type: str, payload_str: str) -> bool:
    if not is_supabase_configured():
        return False
    try:
        payload = {
            "learner_id": learner_id,
            "event_type": event_type,
            "payload": payload_str
        }
        with httpx.Client(timeout=8.0) as client:
            res = client.post(_get_rest_url("learner_events"), json=payload, headers=_get_headers())
            return res.is_success
    except Exception as exc:
        logger.error(f"Supabase log_event error: {exc}")
    return False


def supabase_log_llm(prompt: str, response: str, context: Optional[str] = None) -> bool:
    if not is_supabase_configured():
        return False
    try:
        payload = {
            "prompt": prompt,
            "response": response,
            "context": context or ""
        }
        with httpx.Client(timeout=8.0) as client:
            res = client.post(_get_rest_url("llm_log"), json=payload, headers=_get_headers())
            return res.is_success
    except Exception as exc:
        logger.error(f"Supabase log_llm error: {exc}")
    return False
