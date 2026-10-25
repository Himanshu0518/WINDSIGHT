"""WindSight API routes.

All analysis endpoints serve the pre-validated dataset loaded at startup; none
of them call Elexon. Invalid query parameters produce ``400`` responses with a
clear message, and a missing dataset produces ``503`` (never a stack trace).
"""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.config import get_settings
from app.schemas.forecast import (
    AccuracyResponse,
    DailyMetric,
    EvolutionPoint,
    EvolutionPublication,
    ForecastEvolutionResponse,
    ForecastsResponse,
    HealthResponse,
    IntervalPoint,
    MetricsModel,
    OverviewResponse,
)
from app.services.data_loader import DataUnavailable, get_store
from app.services.forecast_selection import Interval
from app.services.metrics import Metrics

router = APIRouter()


# --- helpers -------------------------------------------------------------
def _store():
    """Return the loaded dataset or raise a 503."""
    try:
        return get_store()
    except DataUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Analysis dataset unavailable: {exc}",
        ) from exc


def _require_delivery_date(value: date | None, settings) -> date:
    if value is None:
        raise HTTPException(
            status_code=400,
            detail="Query parameter 'date' is required (format YYYY-MM-DD).",
        )
    if not settings.is_delivery_date(value):
        raise HTTPException(
            status_code=400,
            detail=(
                f"'date' must be between {settings.delivery_from.isoformat()} and "
                f"{settings.delivery_to.isoformat()}; this dataset covers the "
                "January 2026 delivery period."
            ),
        )
    return value


def _require_range(date_from: date | None, date_to: date | None, settings) -> tuple[date, date]:
    start = date_from or settings.delivery_from
    end = date_to or settings.delivery_to
    if start > end:
        raise HTTPException(
            status_code=400,
            detail=f"'from' ({start.isoformat()}) must be on or before 'to' ({end.isoformat()}).",
        )
    if not settings.is_delivery_date(start) or not settings.is_delivery_date(end):
        raise HTTPException(
            status_code=400,
            detail=(
                f"The requested range must be inside "
                f"{settings.delivery_from.isoformat()}..{settings.delivery_to.isoformat()}; "
                "this dataset covers the January 2026 delivery period."
            ),
        )
    return start, end


def _interval_point(interval: Interval) -> IntervalPoint:
    return IntervalPoint(
        start_time=interval.start_time,
        forecast_mw=interval.forecast_mw,
        actual_mw=interval.actual_mw,
        error_mw=interval.error_mw,
        forecast_publish_time=interval.forecast_publish_time,
        has_forecast=interval.has_forecast,
        has_actual=interval.has_actual,
    )


def _metrics_model(metrics: Metrics) -> MetricsModel:
    return MetricsModel(**metrics.as_dict())


# --- endpoints -----------------------------------------------------------
@router.get("/health", response_model=HealthResponse, tags=["service"])
def health() -> HealthResponse:
    """Service health and data availability (always HTTP 200)."""
    try:
        store = get_store()
    except DataUnavailable as exc:
        return HealthResponse(
            status="degraded",
            service="windsight-api",
            version="1.0.0",
            data_loaded=False,
            detail=str(exc),
        )
    return HealthResponse(
        status="ok",
        service="windsight-api",
        version="1.0.0",
        data_loaded=True,
        generated_at=store.generated_at,
        delivery_from=store.delivery_from,
        delivery_to=store.delivery_to,
        expected_intervals=store.expected_intervals,
        loaded_intervals=len(store.intervals),
        coverage_percent=store.coverage.get("coverage_percent"),
        decision_cutoff=store.cutoff.description,
    )


@router.get("/api/overview", response_model=OverviewResponse, tags=["analysis"])
def overview(
    date: Annotated[date | None, Query(description="Delivery date (YYYY-MM-DD)")] = None,
) -> OverviewResponse:
    """Forecast summary and headline accuracy metrics for a delivery date."""
    settings = get_settings()
    delivery_date = _require_delivery_date(date, settings)
    store = _store()

    intervals = store.intervals_for_date(delivery_date)
    if not intervals:
        raise HTTPException(
            status_code=404,
            detail=f"No intervals loaded for {delivery_date.isoformat()}.",
        )

    publish_times = [
        i.forecast_publish_time for i in intervals if i.forecast_publish_time is not None
    ]
    first_publish = min(publish_times) if publish_times else None
    latest_publish = max(publish_times) if publish_times else None

    return OverviewResponse(
        delivery_date=delivery_date,
        timezone=store.timezone,
        decision_cutoff=store.cutoff.for_delivery(intervals[0].start_time),
        decision_cutoff_description=store.cutoff.description,
        metrics=_metrics_model(store.metrics(delivery_date, delivery_date)),
        first_forecast_publish_time=first_publish,
        latest_eligible_publish_time=latest_publish,
        has_data=bool(publish_times),
    )


@router.get("/api/forecasts", response_model=ForecastsResponse, tags=["analysis"])
def forecasts(
    date: Annotated[date | None, Query(description="Delivery date (YYYY-MM-DD)")] = None,
) -> ForecastsResponse:
    """Half-hourly selected forecast vs. actual generation for a delivery date."""
    settings = get_settings()
    delivery_date = _require_delivery_date(date, settings)
    store = _store()

    intervals = store.intervals_for_date(delivery_date)
    if not intervals:
        raise HTTPException(
            status_code=404,
            detail=f"No intervals loaded for {delivery_date.isoformat()}.",
        )

    return ForecastsResponse(
        delivery_date=delivery_date,
        timezone=store.timezone,
        decision_cutoff=store.cutoff.for_delivery(intervals[0].start_time),
        decision_cutoff_description=store.cutoff.description,
        resolution_minutes=store.resolution_minutes,
        interval_count=len(intervals),
        intervals=[_interval_point(i) for i in intervals],
    )


@router.get("/api/accuracy", response_model=AccuracyResponse, tags=["analysis"])
def accuracy(
    date_from: Annotated[date | None, Query(alias="from", description="Start delivery date")] = None,
    date_to: Annotated[date | None, Query(alias="to", description="End delivery date (inclusive)")] = None,
) -> AccuracyResponse:
    """Aggregate and daily accuracy metrics for a delivery date range."""
    settings = get_settings()
    start, end = _require_range(date_from, date_to, settings)
    store = _store()

    daily = [
        DailyMetric(delivery_date=day, metrics=_metrics_model(metrics))
        for day, metrics in store.daily_metrics(start, end)
    ]
    return AccuracyResponse(
        date_from=start,
        date_to=end,
        timezone=store.timezone,
        summary=_metrics_model(store.metrics(start, end)),
        daily=daily,
    )


@router.get("/api/forecast-evolution", response_model=ForecastEvolutionResponse, tags=["analysis"])
def forecast_evolution(
    date: Annotated[date | None, Query(description="Delivery date (YYYY-MM-DD)")] = None,
) -> ForecastEvolutionResponse:
    """Every forecast publication for a delivery date, oldest first.

    Shows how the day-ahead forecast was revised as delivery approached; the
    ``eligible_before_cutoff`` flag marks the versions available at the
    purchasing decision.
    """
    settings = get_settings()
    delivery_date = _require_delivery_date(date, settings)
    store = _store()

    publications = store.evolution(delivery_date)
    day_start = datetime.combine(delivery_date, time.min, tzinfo=timezone.utc)
    cutoff = store.cutoff.for_delivery(day_start)

    return ForecastEvolutionResponse(
        delivery_date=delivery_date,
        timezone=store.timezone,
        decision_cutoff=cutoff,
        decision_cutoff_description=store.cutoff.description,
        publication_count=len(publications),
        publications=[
            EvolutionPublication(
                publish_time=entry["publish_time"],
                eligible_before_cutoff=entry["eligible_before_cutoff"],
                points=[
                    EvolutionPoint(start_time=p["start_time"], forecast_mw=p["forecast_mw"])
                    for p in entry["points"]
                ],
            )
            for entry in publications
        ],
    )
