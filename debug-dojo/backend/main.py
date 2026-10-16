"""
Vercel FastAPI entrypoint.
Exposes the FastAPI `app` from app.main.
"""

from app.main import app

__all__ = ["app"]
