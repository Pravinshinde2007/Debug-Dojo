import sqlite3
import os
import hashlib
import secrets
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
import jwt

JWT_SECRET = os.environ.get("JWT_SECRET", "debug_dojo_jwt_secret_key_2026_secured_key")
JWT_ALGORITHM = "HS256"

BASE_DIR = Path(__file__).resolve().parent.parent

# On Vercel serverless, the root filesystem is read-only; use /tmp for SQLite and logs
IS_VERCEL = bool(os.environ.get("VERCEL"))
if IS_VERCEL:
    DB_PATH = os.environ.get("DEBUG_DOJO_DB", "/tmp/debug_dojo.db")
    LOGS_DIR = Path("/tmp/logs")
else:
    DB_PATH = os.environ.get("DEBUG_DOJO_DB", str(BASE_DIR / "debug_dojo.db"))
    LOGS_DIR = BASE_DIR / "logs"

LLM_LOG_FILE = LOGS_DIR / "llm.jsonl"


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except Exception:
        pass
    conn.row_factory = sqlite3.Row
    return conn


def hash_password(password: str) -> Tuple[str, str]:
    """Generates a salt and PBKDF2 HMAC SHA-256 password hash."""
    salt = secrets.token_hex(16)
    pw_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000).hex()
    return pw_hash, salt


def verify_password(password: str, password_hash: str, salt: str) -> bool:
    """Verifies a plain password against stored hash and salt."""
    pw_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000).hex()
    return pw_hash == password_hash


def create_user(name: str, email: str, password: str) -> Dict[str, Any]:
    """Registers a new user into SQLite users table."""
    email_clean = email.strip().lower()
    name_clean = name.strip() or email_clean.split("@")[0]
    user_id = str(uuid.uuid4())
    pw_hash, salt = hash_password(password)

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO users (id, name, email, password_hash, salt)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, name_clean, email_clean, pw_hash, salt)
        )
        conn.commit()

    return {"id": user_id, "name": name_clean, "email": email_clean}


def authenticate_user(email: str, password: str) -> Optional[Dict[str, Any]]:
    """Authenticates email and password. Returns user dict on success, None on failure."""
    email_clean = email.strip().lower()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, email, password_hash, salt, created_at FROM users WHERE email = ?", (email_clean,))
        row = cursor.fetchone()
        if not row:
            return None
        if not verify_password(password, row["password_hash"], row["salt"]):
            return None
        return {
            "id": row["id"],
            "name": row["name"],
            "email": row["email"],
            "created_at": row["created_at"]
        }


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Retrieves user info by email without password hash."""
    email_clean = email.strip().lower()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, email, created_at FROM users WHERE email = ?", (email_clean,))
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "name": row["name"],
            "email": row["email"],
            "created_at": row["created_at"]
        }


def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves user info by id without password hash."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, email, created_at FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "name": row["name"],
            "email": row["email"],
            "created_at": row["created_at"]
        }


def create_jwt_token(user_id: str, email: str, name: str, expires_in_seconds: int = 86400 * 7) -> str:
    """Creates a signed JWT token and stores it in SQLite user_tokens table."""
    now = datetime.now(timezone.utc)
    exp = now + timedelta(seconds=expires_in_seconds)
    payload = {
        "sub": user_id,
        "email": email,
        "name": name,
        "jti": uuid.uuid4().hex,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp())
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO user_tokens (user_id, token, expires_at, revoked)
            VALUES (?, ?, ?, 0)
            """,
            (user_id, token, exp.isoformat())
        )
        conn.commit()
    return token


def verify_jwt_token(token: str) -> Optional[Dict[str, Any]]:
    """Verifies a JWT token signature and confirms it exists and is unrevoked in SQLite."""
    if not token:
        return None
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except Exception:
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, user_id, expires_at, revoked FROM user_tokens WHERE token = ?",
            (token,)
        )
        row = cursor.fetchone()
        if not row or row["revoked"] == 1:
            return None

    return get_user_by_id(user_id)


def revoke_jwt_token(token: str) -> bool:
    """Revokes a JWT token in the database upon logout."""
    if not token:
        return False
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE user_tokens SET revoked = 1 WHERE token = ?", (token,))
        conn.commit()
        return cursor.rowcount > 0


def init_db():
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # 0. users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 0b. user_tokens table (stores JWT tokens in SQLite)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                token TEXT UNIQUE NOT NULL,
                expires_at TEXT NOT NULL,
                revoked INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        # 1. submissions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS submissions (
                id TEXT PRIMARY KEY,
                learner_id TEXT NOT NULL,
                challenge_id TEXT NOT NULL,
                code TEXT NOT NULL,
                visible_results TEXT NOT NULL,
                hidden_results TEXT NOT NULL,
                mistake_tags TEXT NOT NULL,
                explanation TEXT NOT NULL,
                passed INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 2. hints_given table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS hints_given (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                submission_id TEXT NOT NULL,
                learner_id TEXT NOT NULL,
                hint_index INTEGER NOT NULL,
                hint_text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 3. learner_events table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS learner_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                learner_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 4. llm_log table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS llm_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prompt TEXT NOT NULL,
                response TEXT NOT NULL,
                context TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()


def log_llm_call(prompt: str, response: str, context: Optional[str] = None):
    # Rule 7: Log every LLM prompt and response to backend/logs/llm.jsonl
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        import json
        import time
        log_entry = {
            "timestamp": time.time(),
            "prompt": prompt,
            "response": response,
            "context": context or ""
        }
        with open(LLM_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")

        # Also log to SQLite table llm_log
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO llm_log (prompt, response, context) VALUES (?, ?, ?)",
                (prompt, response, context or "")
            )
            conn.commit()
    except Exception as exc:
        print(f"Non-fatal logging warning: {exc}")


init_db()
