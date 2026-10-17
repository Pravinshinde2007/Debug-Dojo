import os
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent

backend_candidates = [
    CURRENT_DIR,
    CURRENT_DIR / "app",
    PROJECT_ROOT / "backend",
    PROJECT_ROOT / "debug-dojo" / "backend",
    CURRENT_DIR.parent / "backend",
    Path("/var/task/debug-dojo/backend"),
    Path("/var/task/backend")
]

for candidate in backend_candidates:
    if candidate.exists() and str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import tempfile

safe_temp = Path(tempfile.gettempdir()) / "debug_dojo.db"
os.environ.setdefault("DEBUG_DOJO_DB", str(safe_temp))

try:
    from app.main import app
    try:
        from app.db import init_db
        init_db()
    except Exception:
        pass
except Exception as e:
    import traceback
    err_tb = traceback.format_exc()
    print("Error importing app.main in debug-dojo/api/index.py:\n", err_tb)
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    app = FastAPI(title="Debug Dojo API (Fallback)")

    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"])
    async def fallback_handler(path: str):
        return JSONResponse(
            status_code=500,
            content={
                "error": True,
                "detail": f"Backend initialization error: {str(e)}",
                "traceback": err_tb
            }
        )

