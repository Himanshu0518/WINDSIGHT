"""WindSight FastAPI application factory.

The analysis dataset is loaded once at startup (see ``lifespan``) and served
from memory. CORS is restricted to the origins configured through
``CORS_ORIGINS`` so the deployed frontend is the only allowed caller.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import get_settings
from app.services.data_loader import DataUnavailable, init_store

logger = logging.getLogger(__name__)

SERVICE_NAME = "windsight-api"
SERVICE_VERSION = "1.0.0"

DESCRIPTION = """
WindSight - day-ahead wind forecast intelligence for UK power procurement.

* Actual generation: Elexon BMRS `FUELHH` (half-hourly, WIND, MW)
* Forecasts: Elexon BMRS `WINDFOR` (hourly, all published versions)
* Decision rule: latest forecast published at or before 10:00 Europe/London
  on the day before delivery.
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load the validated dataset once; serve 503s if it is unavailable."""
    try:
        init_store(get_settings())
    except DataUnavailable as exc:
        logger.error("Analysis dataset unavailable: %s", exc)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="WindSight API",
        version=SERVICE_VERSION,
        description=DESCRIPTION,
        lifespan=lifespan,
    )

    origins = list(settings.cors_origins)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    app.include_router(router)

    @app.get("/", tags=["service"])
    def root() -> dict:
        return {
            "service": SERVICE_NAME,
            "version": SERVICE_VERSION,
            "docs": "/docs",
            "health": "/health",
        }

    return app


app = create_app()
