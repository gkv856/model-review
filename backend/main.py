"""
Entry point — re-exports `app` from api/app.py for backward compatibility.

Start the server:
  uvicorn main:app --reload --port 8000
  or
  uvicorn api.app:app --reload --port 8000
"""

from api.app import app

__all__ = ["app"]
