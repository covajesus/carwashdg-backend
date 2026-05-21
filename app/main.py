"""ASGI entry for production (e.g. uvicorn app.main:app).

The FastAPI application is defined in main.py at the project root.
"""

from main import app

__all__ = ["app"]
