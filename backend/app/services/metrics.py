"""Accuracy metrics for forecast vs. actual wind generation.

Definitions (``F_t`` = forecast MW, ``A_t`` = actual MW, ``e_t = F_t - A_t``):

* ``MAE   = mean(|e_t|)``
* ``RMSE  = sqrt(mean(e_t^2))``
* ``Bias  = mean(e_t)`` - positive means the forecast overestimated wind.
* ``MAPE  = mean(|e_t| / |A_t|) * 100`` computed **only** over matched
  intervals whose actual generation is non-zero. Zero-actual intervals are
  excluded because the percentage denominator would be undefined; the count
  of excluded intervals is reported alongside ``mape_percent``.

Missing-data policy: an interval enters an error metric only when **both**
forecast and actual exist. Missing values are never coerced to zero - they
are counted in ``missing_forecast_intervals`` / ``missing_actual_intervals``
and reflected in ``coverage_percent``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import Sequence

from app.services.forecast_selection import Interval
from app.timeutils import local_date


@dataclass(frozen=True)
class Metrics:
    """Aggregate accuracy metrics over a set of delivery intervals."""

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

    def as_dict(self) -> dict:
        return {
            "total_intervals": self.total_intervals,
            "matched_intervals": self.matched_intervals,
            "missing_forecast_intervals": self.missing_forecast_intervals,
            "missing_actual_intervals": self.missing_actual_intervals,
            "mape_excluded_intervals": self.mape_excluded_intervals,
            "coverage_percent": self.coverage_percent,
            "mae_mw": self.mae_mw,
            "rmse_mw": self.rmse_mw,
            "bias_mw": self.bias_mw,
            "mape_percent": self.mape_percent,
        }


def summarise(intervals: Sequence[Interval]) -> Metrics:
    """Compute accuracy metrics over ``intervals``."""
    total = len(intervals)
    missing_forecast = 0
    missing_actual = 0
    errors: list[float] = []
    percentage_errors: list[float] = []
    mape_excluded = 0

    for interval in intervals:
        if not interval.has_forecast:
            missing_forecast += 1
        if not interval.has_actual:
            missing_actual += 1
        if interval.forecast_mw is None or interval.actual_mw is None:
            continue  # missing data is excluded, never treated as zero
        error = interval.forecast_mw - interval.actual_mw
        errors.append(error)
        if interval.actual_mw == 0:
            mape_excluded += 1
        else:
            percentage_errors.append(abs(error) / abs(interval.actual_mw) * 100.0)

    matched = len(errors)
    coverage = round(matched / total * 100.0, 2) if total else None

    if matched == 0:
        return Metrics(
            total_intervals=total,
            matched_intervals=0,
            missing_forecast_intervals=missing_forecast,
            missing_actual_intervals=missing_actual,
            mape_excluded_intervals=mape_excluded,
            coverage_percent=coverage,
            mae_mw=None,
            rmse_mw=None,
            bias_mw=None,
            mape_percent=None,
        )

    mae = sum(abs(e) for e in errors) / matched
    rmse = math.sqrt(sum(e * e for e in errors) / matched)
    bias = sum(errors) / matched
    mape = (
        round(sum(percentage_errors) / len(percentage_errors), 2)
        if percentage_errors
        else None
    )

    return Metrics(
        total_intervals=total,
        matched_intervals=matched,
        missing_forecast_intervals=missing_forecast,
        missing_actual_intervals=missing_actual,
        mape_excluded_intervals=mape_excluded,
        coverage_percent=coverage,
        mae_mw=round(mae, 3),
        rmse_mw=round(rmse, 3),
        bias_mw=round(bias, 3),
        mape_percent=mape,
    )


def daily_summaries(
    intervals: Sequence[Interval], tz_name: str = "Europe/London"
) -> list[tuple[date, Metrics]]:
    """Per-delivery-day metrics, ordered by date.

    Daily and monthly summaries use the same inclusion rules (see
    :func:`summarise`), so the monthly MAE equals the count-weighted mean of
    the daily MAEs.
    """
    buckets: dict[date, list[Interval]] = {}
    for interval in intervals:
        buckets.setdefault(local_date(interval.start_time, tz_name), []).append(interval)
    return [(day, summarise(buckets[day])) for day in sorted(buckets)]
