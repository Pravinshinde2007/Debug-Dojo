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

def _is_read_only_env() -> bool:
    if os.environ.get("VERCEL") or os.environ.get("VERCEL_ENV") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        return True
    try:
        test_file = BASE_DIR / ".write_test"
        test_file.touch()
        test_file.unlink()
        return False
    except Exception:
        return True

if _is_read_only_env():
    DB_PATH = os.environ.get("DEBUG_DOJO_DB", "/tmp/debug_dojo.db")
    LOGS_DIR = Path("/tmp/logs")
else:
    DB_PATH = os.environ.get("DEBUG_DOJO_DB", str(BASE_DIR / "debug_dojo.db"))
    LOGS_DIR = BASE_DIR / "logs"

LLM_LOG_FILE = LOGS_DIR / "llm.jsonl"
_is_initializing_schema = False


def get_db_connection() -> sqlite3.Connection:
    global DB_PATH, _is_initializing_schema
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30.0)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
        except Exception:
            pass
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        if DB_PATH != "/tmp/debug_dojo.db" and not _is_initializing_schema:
            DB_PATH = "/tmp/debug_dojo.db"
            conn = sqlite3.connect(DB_PATH, timeout=30.0)
            conn.row_factory = sqlite3.Row
            try:
                _is_initializing_schema = True
                init_db()
            except Exception:
                pass
            finally:
                _is_initializing_schema = False
            return conn
        raise e


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
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
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

        # 5. sandbox_attempts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sandbox_attempts (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                problem_title TEXT NOT NULL,
                problem_statement TEXT,
                problem_spec TEXT,
                language TEXT NOT NULL,
                code TEXT NOT NULL,
                mode TEXT NOT NULL,
                passed INTEGER NOT NULL DEFAULT 0,
                test_results TEXT NOT NULL,
                feedback TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Seed default demo student account if not present
        cursor.execute("SELECT id FROM users WHERE email = 'student@debugdojo.dev'")
        if not cursor.fetchone():
            pwd_hash, salt = hash_password("dojopass2026")
            cursor.execute(
                "INSERT INTO users (id, name, email, password_hash, salt) VALUES (?, ?, ?, ?, ?)",
                ("usr_demo_student", "Demo Student", "student@debugdojo.dev", pwd_hash, salt)
            )

        conn.commit()


def save_sandbox_attempt(
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
) -> str:
    attempt_id = str(uuid.uuid4())
    import json
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO sandbox_attempts (
                id, user_id, problem_title, problem_statement, problem_spec,
                language, code, mode, passed, test_results, feedback
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                attempt_id,
                user_id,
                problem_title,
                problem_statement,
                json.dumps(problem_spec),
                language,
                code,
                mode,
                1 if passed else 0,
                json.dumps(test_results),
                json.dumps(feedback)
            )
        )
        conn.commit()
    return attempt_id


def get_sandbox_attempts(user_id: str, limit: int = 20) -> list:
    import json
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, user_id, problem_title, problem_statement, problem_spec,
                   language, code, mode, passed, test_results, feedback, created_at
            FROM sandbox_attempts
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (user_id, limit)
        )
        rows = cursor.fetchall()
        result = []
        for r in rows:
            result.append({
                "id": r["id"],
                "user_id": r["user_id"],
                "problem_title": r["problem_title"],
                "problem_statement": r["problem_statement"],
                "problem_spec": json.loads(r["problem_spec"]) if r["problem_spec"] else {},
                "language": r["language"],
                "code": r["code"],
                "mode": r["mode"],
                "passed": bool(r["passed"]),
                "test_results": json.loads(r["test_results"]) if r["test_results"] else {},
                "feedback": json.loads(r["feedback"]) if r["feedback"] else {},
                "created_at": r["created_at"]
            })
        return result


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

