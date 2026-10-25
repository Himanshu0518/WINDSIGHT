"""Pydantic response models for the WindSight API.

Timestamps are timezone-aware UTC datetimes and serialise as ISO-8601 with a
``Z`` suffix. ``None`` values mean *missing data* - they are never replaced
with zero.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class IntervalPoint(BaseModel):
    """One half-hour delivery interval with its selected forecast and actual."""

    model_config = ConfigDict(json_schema_extra={"example": {
        "start_time": "2026-01-15T10:00:00Z",
        "forecast_mw": 5300.0,
        "actual_mw": 4900.0,
        "error_mw": 400.0,
        "forecast_publish_time": "2026-01-14T09:30:00Z",
        "has_forecast": True,
        "has_actual": True,
    }})

    start_time: datetime
    forecast_mw: float | None
    actual_mw: float | None
    error_mw: float | None
    forecast_publish_time: datetime | None
    has_forecast: bool
    has_actual: bool


class ForecastsResponse(BaseModel):
    """Half-hourly forecast/actual series for one delivery date."""

    delivery_date: date
    timezone: str
    decision_cutoff: datetime
    decision_cutoff_description: str
    resolution_minutes: int
    interval_count: int
    intervals: list[IntervalPoint]


class MetricsModel(BaseModel):
    """Accuracy metrics over a set of delivery intervals."""

    total_intervals: int
    matched_intervals: int
    missing_forecast_intervals: int
    missing_actual_intervals: int
    mape_excluded_intervals: int
    coverage_percent: float | None
    mae_mw: float | None
    rmse_mw: float | None
    bias_mw: float | None
    mape_percent: float | None


class OverviewResponse(BaseModel):
    """Forecast summary for a single delivery date."""

    delivery_date: date
    timezone: str
    decision_cutoff: datetime
    decision_cutoff_description: str
    metrics: MetricsModel
    first_forecast_publish_time: datetime | None
    latest_eligible_publish_time: datetime | None
    has_data: bool


class DailyMetric(BaseModel):
    """Metrics for one delivery date (used inside the accuracy response)."""

    delivery_date: date
    metrics: MetricsModel


class AccuracyResponse(BaseModel):
    """Aggregate and daily accuracy metrics for a delivery date range."""

    date_from: date
    date_to: date
    timezone: str
    summary: MetricsModel
    daily: list[DailyMetric]


class EvolutionPoint(BaseModel):
    """One hourly forecast value within a publication."""

    start_time: datetime
    forecast_mw: float | None


class EvolutionPublication(BaseModel):
    """A single forecast publication for a delivery date."""

    publish_time: datetime
    eligible_before_cutoff: bool
    points: list[EvolutionPoint]


class ForecastEvolutionResponse(BaseModel):
    """Every forecast version published for a delivery date, oldest first."""

    delivery_date: date
    timezone: str
    decision_cutoff: datetime
    decision_cutoff_description: str
    publication_count: int
    publications: list[EvolutionPublication]


class HealthResponse(BaseModel):
    """Service health and dataset availability."""

    status: Literal["ok", "degraded"]
    service: str
    version: str
    data_loaded: bool
    detail: str | None = None
    generated_at: datetime | None = None
    delivery_from: date | None = None
    delivery_to: date | None = None
    expected_intervals: int | None = None
    loaded_intervals: int | None = None
    coverage_percent: float | None = None
    decision_cutoff: str | None = None
