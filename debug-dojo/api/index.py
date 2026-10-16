import os
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent

backend_candidates = [
    PROJECT_ROOT / "backend",
    PROJECT_ROOT / "debug-dojo" / "backend",
    CURRENT_DIR.parent / "backend",
    Path("/var/task/debug-dojo/backend"),
    Path("/var/task/backend")
]

for candidate in backend_candidates:
    if candidate.exists() and str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))
        break

os.environ.setdefault("DEBUG_DOJO_DB", "/tmp/debug_dojo.db")

from app.main import app

try:
    from app.db import init_db
    init_db()
except Exception:
    pass
