"""Entry point for `fastapi dev` / `fastapi run` (kept at the project root).

The application itself lives in ``app/main.py``; this module only re-exports
the ASGI app so the FastAPI CLI can discover ``main:app``.
"""

from app.main import app

__all__ = ["app"]
