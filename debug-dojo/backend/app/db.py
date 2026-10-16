import sqlite3
import os
import hashlib
import secrets
import uuid
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

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
    conn = sqlite3.connect(DB_PATH)
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


init_db()
