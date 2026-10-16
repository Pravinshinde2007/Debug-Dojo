import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent

# Check both potential locations for backend
backend_candidates = [
    PROJECT_ROOT / "debug-dojo" / "backend",
    PROJECT_ROOT / "backend",
]

for candidate in backend_candidates:
    if candidate.exists() and str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))
        break

from app.main import app
