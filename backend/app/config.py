"""Configuration for the WindSight backend.

Every setting can be overridden with an environment variable so the same
build runs locally, in Docker and in production without code changes.
See ``.env.example`` in the repository root for the full list.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = BACKEND_DIR / "data"


def _env_str(name: str, default: str) -> str:
    value = os.environ.get(name)
    return default if value is None or value == "" else value


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return int(value)


def _env_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return float(value)


def _env_date(name: str, default: date) -> date:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return date.fromisoformat(value)


def _env_tuple(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return tuple(part.strip() for part in value.split(",") if part.strip())


@dataclass(frozen=True)
class Settings:
    """Runtime settings; see module docstring for the environment variables."""

    # Data
    data_dir: Path = DEFAULT_DATA_DIR

    # Delivery period covered by the dataset
    delivery_from: date = date(2026, 1, 1)
    delivery_to: date = date(2026, 1, 31)

    # Day-ahead purchasing decision cutoff
    decision_cutoff_hour: int = 10
    decision_cutoff_minute: int = 0
    decision_cutoff_timezone: str = "Europe/London"
    decision_cutoff_lead_days: int = 1

    # HTTP
    cors_origins: tuple[str, ...] = (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    )

    # Elexon BMRS API
    elexon_base_url: str = "https://data.elexon.co.uk/bmrs/api/v1"
    elexon_timeout_seconds: float = 30.0
    elexon_max_retries: int = 3

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            data_dir=Path(_env_str("DATA_DIR", str(DEFAULT_DATA_DIR))),
            delivery_from=_env_date("DELIVERY_FROM", date(2026, 1, 1)),
            delivery_to=_env_date("DELIVERY_TO", date(2026, 1, 31)),
            decision_cutoff_hour=_env_int("DECISION_CUTOFF_HOUR", 10),
            decision_cutoff_minute=_env_int("DECISION_CUTOFF_MINUTE", 0),
            decision_cutoff_timezone=_env_str("DECISION_CUTOFF_TIMEZONE", "Europe/London"),
            decision_cutoff_lead_days=_env_int("DECISION_CUTOFF_LEAD_DAYS", 1),
            cors_origins=_env_tuple(
                "CORS_ORIGINS",
                (
                    "http://localhost:5173",
                    "http://127.0.0.1:5173",
                    "http://localhost:3000",
                ),
            ),
            elexon_base_url=_env_str(
                "ELEXON_BASE_URL", "https://data.elexon.co.uk/bmrs/api/v1"
            ),
            elexon_timeout_seconds=_env_float("ELEXON_TIMEOUT_SECONDS", 30.0),
            elexon_max_retries=_env_int("ELEXON_MAX_RETRIES", 3),
        )

    # --- derived paths -------------------------------------------------
    @property
    def analysis_path(self) -> Path:
        return self.data_dir / "analysis.json"

    @property
    def actuals_path(self) -> Path:
        return self.data_dir / "actuals.json"

    @property
    def forecasts_path(self) -> Path:
        return self.data_dir / "forecasts.json"

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    # --- delivery helpers ---------------------------------------------
    @property
    def cutoff_description(self) -> str:
        from app.timeutils import cutoff_description

        return cutoff_description(
            self.decision_cutoff_hour,
            self.decision_cutoff_minute,
            self.decision_cutoff_timezone,
            self.decision_cutoff_lead_days,
        )

    @property
    def cutoff_rule(self):
        from app.services.forecast_selection import CutoffRule

        return CutoffRule(
            hour=self.decision_cutoff_hour,
            minute=self.decision_cutoff_minute,
            tz=self.decision_cutoff_timezone,
            lead_days=self.decision_cutoff_lead_days,
        )

    def is_delivery_date(self, value: date) -> bool:
        return self.delivery_from <= value <= self.delivery_to


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process-wide settings (cached; clear with ``get_settings.cache_clear()``)."""
    return Settings.from_env()
