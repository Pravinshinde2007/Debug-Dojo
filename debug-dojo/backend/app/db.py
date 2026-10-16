import sqlite3
import os
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = os.environ.get("DEBUG_DOJO_DB", str(BASE_DIR / "debug_dojo.db"))
LOGS_DIR = BASE_DIR / "logs"
LLM_LOG_FILE = LOGS_DIR / "llm.log"


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
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
    # Rule 7: Log every LLM prompt and response to a file
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    with open(LLM_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"--- LLM CALL ---\n")
        if context:
            f.write(f"CONTEXT: {context}\n")
        f.write(f"PROMPT:\n{prompt}\n")
        f.write(f"RESPONSE:\n{response}\n")
        f.write(f"{'-' * 40}\n\n")

    # Also log to SQLite table llm_log
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO llm_log (prompt, response, context) VALUES (?, ?, ?)",
            (prompt, response, context or "")
        )
        conn.commit()


# Initialize on import
init_db()
