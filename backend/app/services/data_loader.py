"""Loads the generated analysis dataset produced by ``scripts/download_data.py``.

The API reads ``backend/data/analysis.json`` (matched intervals) and
``backend/data/forecasts.json`` (full forecast history, used by the
forecast-evolution endpoint) once at startup and serves filtered results from
memory - it never calls Elexon while serving a page.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from app.config import Settings, get_settings
from app.services.forecast_selection import (
    CutoffRule,
    ForecastIndex,
    Interval,
    filter_intervals,
)
from app.services.metrics import Metrics, daily_summaries, summarise
from app.timeutils import expected_interval_count, parse_utc

logger = logging.getLogger(__name__)


class DataUnavailable(RuntimeError):
    """Raised when the analysis dataset is missing or unreadable."""


@dataclass
class AnalysisStore:
    """In-memory view of the validated WindSight dataset."""

    generated_at: datetime | None
    delivery_from: date
    delivery_to: date
    timezone: str
    cutoff: CutoffRule
    resolution_minutes: int
    intervals: list[Interval]
    forecast_index: ForecastIndex
    source: dict = field(default_factory=dict)

    # --- interval access ----------------------------------------------
    @property
    def expected_intervals(self) -> int:
        return expected_interval_count(self.delivery_from, self.delivery_to)

    def intervals_for_range(
        self, date_from: date | None = None, date_to: date | None = None
    ) -> list[Interval]:
        return filter_intervals(self.intervals, date_from, date_to, self.timezone)

    def intervals_for_date(self, delivery_date: date) -> list[Interval]:
        return self.intervals_for_range(delivery_date, delivery_date)

    # --- metrics -------------------------------------------------------
    def metrics(
        self, date_from: date | None = None, date_to: date | None = None
    ) -> Metrics:
        return summarise(self.intervals_for_range(date_from, date_to))

    def daily_metrics(
        self, date_from: date | None = None, date_to: date | None = None
    ) -> list[tuple[date, Metrics]]:
        return daily_summaries(self.intervals_for_range(date_from, date_to), self.timezone)

    # --- forecast evolution --------------------------------------------
    def evolution(self, delivery_date: date) -> list[dict]:
        """Every publication that forecast the given delivery day, oldest first.

        Each entry carries its hourly points plus a flag marking whether the
        publication was still eligible under the decision cutoff.
        """
        window_start = datetime.combine(delivery_date, datetime.min.time(), tzinfo=timezone.utc)
        window_end = window_start + timedelta(days=1)
        cutoff = self.cutoff.for_delivery(window_start)
        series = self.forecast_index.series_for_window(window_start, window_end)
        return [
            {
                "publish_time": publish,
                "eligible_before_cutoff": publish <= cutoff,
                "points": [
                    {"start_time": record.start_time, "forecast_mw": record.generation_mw}
                    for record in records
                ],
            }
            for publish, records in series
        ]

    # --- metadata -------------------------------------------------------
    @property
    def coverage(self) -> dict:
        metrics = self.metrics()
        return {
            "expected_intervals": self.expected_intervals,
            "loaded_intervals": len(self.intervals),
            "matched_intervals": metrics.matched_intervals,
            "missing_forecast_intervals": metrics.missing_forecast_intervals,
            "missing_actual_intervals": metrics.missing_actual_intervals,
            "coverage_percent": metrics.coverage_percent,
        }


# --- loading -------------------------------------------------------------
_store: AnalysisStore | None = None


def _read_json(path: Path):
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise DataUnavailable(
            f"Missing data file {path}. Run `uv run --project backend python "
            f"scripts/download_data.py` to download it from Elexon."
        ) from exc
    except json.JSONDecodeError as exc:
        raise DataUnavailable(f"Data file {path} is not valid JSON: {exc}") from exc


def load_store(settings: Settings | None = None) -> AnalysisStore:
    """Load the analysis dataset from disk (raises :class:`DataUnavailable`)."""
    settings = settings or get_settings()
    analysis = _read_json(settings.analysis_path)

    delivery = analysis.get("delivery", {})
    delivery_from = date.fromisoformat(str(delivery.get("from", settings.delivery_from)))
    delivery_to = date.fromisoformat(str(delivery.get("to", settings.delivery_to)))
    timezone_name = str(delivery.get("timezone", settings.decision_cutoff_timezone))

    cutoff_config = analysis.get("decision_cutoff", {})
    cutoff = CutoffRule(
        hour=int(cutoff_config.get("hour", settings.decision_cutoff_hour)),
        minute=int(cutoff_config.get("minute", settings.decision_cutoff_minute)),
        tz=str(cutoff_config.get("timezone", timezone_name)),
        lead_days=int(cutoff_config.get("lead_days", settings.decision_cutoff_lead_days)),
    )

    intervals: list[Interval] = []
    for row in analysis.get("intervals", []):
        start = parse_utc(row.get("start_time"))
        if start is None:
            continue
        forecast = row.get("forecast_mw")
        actual = row.get("actual_mw")
        intervals.append(
            Interval(
                start_time=start,
                forecast_mw=None if forecast is None else float(forecast),
                actual_mw=None if actual is None else float(actual),
                forecast_publish_time=parse_utc(row.get("forecast_publish_time")),
            )
        )
    if not intervals:
        raise DataUnavailable(
            f"{settings.analysis_path} contains no delivery intervals; "
            "re-run scripts/download_data.py."
        )

    # Forecast history is optional: only the evolution endpoint needs it.
    forecast_index = ForecastIndex([])
    if settings.forecasts_path.exists():
        forecasts_payload = _read_json(settings.forecasts_path)
        forecast_index = ForecastIndex.from_dicts(forecasts_payload.get("records", []))
    else:
        logger.warning(
            "%s not found; forecast-evolution endpoint will return no data.",
            settings.forecasts_path,
        )

    store = AnalysisStore(
        generated_at=parse_utc(analysis.get("generated_at")),
        delivery_from=delivery_from,
        delivery_to=delivery_to,
        timezone=timezone_name,
        cutoff=cutoff,
        resolution_minutes=int(delivery.get("resolution_minutes", 30)),
        intervals=intervals,
        forecast_index=forecast_index,
        source=analysis.get("source", {}),
    )
    logger.info(
        "Loaded %s intervals (%s expected) for %s..%s",
        len(store.intervals),
        store.expected_intervals,
        delivery_from,
        delivery_to,
    )
    return store


def init_store(settings: Settings | None = None) -> AnalysisStore:
    """Load the dataset and cache it as the process-wide store."""
    global _store
    _store = load_store(settings)
    return _store


def get_store() -> AnalysisStore:
    """Return the cached store, loading it on first use.

    Raises :class:`DataUnavailable` when no dataset can be loaded.
    """
    global _store
    if _store is None:
        return init_store()
    return _store


def set_store(store: AnalysisStore | None) -> None:
    """Replace the cached store (used by tests and the download script)."""
    global _store
    _store = store


def reset_store() -> None:
    """Drop the cached store so the next request reloads from disk."""
    set_store(None)
