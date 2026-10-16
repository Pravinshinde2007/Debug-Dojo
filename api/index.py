import os
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent

# Check potential locations for backend across various deployment layouts
backend_candidates = [
    PROJECT_ROOT / "debug-dojo" / "backend",
    PROJECT_ROOT / "backend",
    CURRENT_DIR.parent / "backend",
    CURRENT_DIR.parent / "debug-dojo" / "backend",
    Path("/var/task/debug-dojo/backend"),
    Path("/var/task/backend")
]

for candidate in backend_candidates:
    if candidate.exists() and str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))
        break

# Default to /tmp SQLite database on Vercel serverless
os.environ.setdefault("DEBUG_DOJO_DB", "/tmp/debug_dojo.db")

from app.main import app

# Ensure SQLite schema is prepared on serverless cold starts
try:
    from app.db import init_db
    init_db()
except Exception:
    pass
