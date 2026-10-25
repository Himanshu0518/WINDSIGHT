"""Configuration for the WindSight backend.

Every setting can be overridden with an environment variable or specified in
a `.env` file so the same build runs locally, in Docker, and in production
without code changes.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from dotenv import load_dotenv

if TYPE_CHECKING:
    from app.services.forecast_selection import CutoffRule

# ---------------------------------------------------------------------------
# Directory Paths & Dotenv Loading
# ---------------------------------------------------------------------------
BACKEND_DIR = Path(__file__).resolve().parents[1]

# Load variables from backend/.env first, then root .env if present
load_dotenv(BACKEND_DIR / ".env")
load_dotenv(BACKEND_DIR.parent / ".env")

# ---------------------------------------------------------------------------
# Default Configuration Constants
# ---------------------------------------------------------------------------
DEFAULT_DATA_DIR = BACKEND_DIR / "data"

DEFAULT_DELIVERY_FROM = date(2026, 1, 1)
DEFAULT_DELIVERY_TO = date(2026, 1, 31)

DEFAULT_DECISION_CUTOFF_HOUR = 10
DEFAULT_DECISION_CUTOFF_MINUTE = 0
DEFAULT_DECISION_CUTOFF_TIMEZONE = "Europe/London"
DEFAULT_DECISION_CUTOFF_LEAD_DAYS = 1

DEFAULT_CORS_ORIGINS: tuple[str, ...] = (
   
    "https://wind-sight-flax.vercel.app",
     "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
)

DEFAULT_ELEXON_BASE_URL = "https://data.elexon.co.uk/bmrs/api/v1"
DEFAULT_ELEXON_TIMEOUT_SECONDS = 30.0
DEFAULT_ELEXON_MAX_RETRIES = 3


# ---------------------------------------------------------------------------
# Environment Variable Parsing Helpers
# ---------------------------------------------------------------------------
def _env_str(name: str, default: str) -> str:
    """Read a string environment variable with fallback."""
    val = os.environ.get(name)
    return default if val is None or val.strip() == "" else val.strip()


def _env_int(name: str, default: int) -> int:
    """Read an integer environment variable with fallback."""
    val = os.environ.get(name)
    if val is None or val.strip() == "":
        return default
    try:
        return int(val.strip())
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    """Read a float environment variable with fallback."""
    val = os.environ.get(name)
    if val is None or val.strip() == "":
        return default
    try:
        return float(val.strip())
    except ValueError:
        return default


def _env_date(name: str, default: date) -> date:
    """Read an ISO-formatted date (YYYY-MM-DD) with fallback."""
    val = os.environ.get(name)
    if val is None or val.strip() == "":
        return default
    try:
        return date.fromisoformat(val.strip())
    except ValueError:
        return default


def _env_tuple(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    """Read a comma-separated list of strings, stripping spaces and trailing slashes."""
    val = os.environ.get(name)
    if val is None or val.strip() == "":
        return default
    # Normalise items (strip whitespace and trailing slashes for clean URL / origin matches)
    cleaned = [part.strip().rstrip("/") for part in val.split(",") if part.strip()]
    return tuple(cleaned) if cleaned else default


# ---------------------------------------------------------------------------
# Settings Container
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Settings:
    """Runtime configuration container for WindSight API."""

    # Storage paths
    data_dir: Path = DEFAULT_DATA_DIR

    # Delivery period window
    delivery_from: date = DEFAULT_DELIVERY_FROM
    delivery_to: date = DEFAULT_DELIVERY_TO

    # Day-ahead decision cutoff rules
    decision_cutoff_hour: int = DEFAULT_DECISION_CUTOFF_HOUR
    decision_cutoff_minute: int = DEFAULT_DECISION_CUTOFF_MINUTE
    decision_cutoff_timezone: str = DEFAULT_DECISION_CUTOFF_TIMEZONE
    decision_cutoff_lead_days: int = DEFAULT_DECISION_CUTOFF_LEAD_DAYS

    # CORS Allowed Origins
    cors_origins: tuple[str, ...] = DEFAULT_CORS_ORIGINS

    # Elexon BMRS API client settings
    elexon_base_url: str = DEFAULT_ELEXON_BASE_URL
    elexon_timeout_seconds: float = DEFAULT_ELEXON_TIMEOUT_SECONDS
    elexon_max_retries: int = DEFAULT_ELEXON_MAX_RETRIES

    @classmethod
    def from_env(cls) -> Settings:
        """Construct Settings populated from active environment variables or defaults."""
        return cls(
            data_dir=Path(_env_str("DATA_DIR", str(DEFAULT_DATA_DIR))),
            delivery_from=_env_date("DELIVERY_FROM", DEFAULT_DELIVERY_FROM),
            delivery_to=_env_date("DELIVERY_TO", DEFAULT_DELIVERY_TO),
            decision_cutoff_hour=_env_int("DECISION_CUTOFF_HOUR", DEFAULT_DECISION_CUTOFF_HOUR),
            decision_cutoff_minute=_env_int("DECISION_CUTOFF_MINUTE", DEFAULT_DECISION_CUTOFF_MINUTE),
            decision_cutoff_timezone=_env_str("DECISION_CUTOFF_TIMEZONE", DEFAULT_DECISION_CUTOFF_TIMEZONE),
            decision_cutoff_lead_days=_env_int("DECISION_CUTOFF_LEAD_DAYS", DEFAULT_DECISION_CUTOFF_LEAD_DAYS),
            cors_origins=_env_tuple("CORS_ORIGINS", DEFAULT_CORS_ORIGINS),
            elexon_base_url=_env_str("ELEXON_BASE_URL", DEFAULT_ELEXON_BASE_URL),
            elexon_timeout_seconds=_env_float("ELEXON_TIMEOUT_SECONDS", DEFAULT_ELEXON_TIMEOUT_SECONDS),
            elexon_max_retries=_env_int("ELEXON_MAX_RETRIES", DEFAULT_ELEXON_MAX_RETRIES),
        )

    # -----------------------------------------------------------------------
    # Derived Data File Paths
    # -----------------------------------------------------------------------
    @property
    def analysis_path(self) -> Path:
        """Full path to analysis.json."""
        return self.data_dir / "analysis.json"

    @property
    def actuals_path(self) -> Path:
        """Full path to actuals.json."""
        return self.data_dir / "actuals.json"

    @property
    def forecasts_path(self) -> Path:
        """Full path to forecasts.json."""
        return self.data_dir / "forecasts.json"

    @property
    def raw_dir(self) -> Path:
        """Directory for raw downloaded Elexon payloads."""
        return self.data_dir / "raw"

    # -----------------------------------------------------------------------
    # Decision Cutoff & Delivery Helpers
    # -----------------------------------------------------------------------
    @property
    def cutoff_description(self) -> str:
        """Human-readable cutoff summary."""
        from app.timeutils import cutoff_description

        return cutoff_description(
            self.decision_cutoff_hour,
            self.decision_cutoff_minute,
            self.decision_cutoff_timezone,
            self.decision_cutoff_lead_days,
        )

    @property
    def cutoff_rule(self) -> CutoffRule:
        """CutoffRule instance representing the decision cutoff."""
        from app.services.forecast_selection import CutoffRule

        return CutoffRule(
            hour=self.decision_cutoff_hour,
            minute=self.decision_cutoff_minute,
            tz=self.decision_cutoff_timezone,
            lead_days=self.decision_cutoff_lead_days,
        )

    def is_delivery_date(self, value: date) -> bool:
        """Check if a date falls inside the delivery window."""
        return self.delivery_from <= value <= self.delivery_to


# ---------------------------------------------------------------------------
# Global Singleton Accessor
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return process-wide cached settings. Clear with ``get_settings.cache_clear()``."""
    return Settings.from_env()
