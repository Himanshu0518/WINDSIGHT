"""Forecast selection and delivery-interval matching (core domain logic).

Decision rule
-------------
The assignment does not fix a purchasing decision time, so it is configurable
(``CutoffRule``). For every delivery interval ``t`` the cutoff ``c_t`` is
10:00 UK local time on the day before delivery, and the selected forecast is

    p* = max { p : p <= c_t }

i.e. the **latest forecast published no later than the cutoff**. If no
forecast satisfies the rule the interval is recorded as missing - a later
(future) forecast is never used, because it would not have been available
when the purchasing decision was made.

Matching
--------
* ``FUELHH`` actuals are half-hourly; ``WINDFOR`` forecasts are hourly, so an
  hourly forecast value is broadcast to both half-hours it covers and the
  duplicate policy is documented rather than implicit.
* Records are matched strictly by timestamp (UTC), never by row position.
* Duplicate records with the same (publish time, target time) are dropped,
  keeping the last occurrence, and counted so ingestion reports them.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable, Mapping, Sequence

from app.timeutils import (
    cutoff_description,
    delivery_slots,
    local_date,
    local_cutoff,
    parse_utc,
)


@dataclass(frozen=True)
class CutoffRule:
    """When the day-ahead purchasing decision must be made."""

    hour: int = 10
    minute: int = 0
    tz: str = "Europe/London"
    lead_days: int = 1

    def for_delivery(self, moment_utc: datetime) -> datetime:
        """UTC cutoff applying to the delivery day containing ``moment_utc``."""
        return local_cutoff(
            moment_utc,
            hour=self.hour,
            minute=self.minute,
            tz_name=self.tz,
            lead_days=self.lead_days,
        )

    @property
    def description(self) -> str:
        return cutoff_description(self.hour, self.minute, self.tz, self.lead_days)


@dataclass(frozen=True)
class ForecastRecord:
    """A single WINDFOR forecast value for one hourly target."""

    publish_time: datetime
    start_time: datetime
    generation_mw: float | None

    @property
    def target_hour(self) -> datetime:
        """Hour-aligned target timestamp (WINDFOR targets are hourly)."""
        return self.start_time.replace(minute=0, second=0, microsecond=0)


@dataclass(frozen=True)
class ActualRecord:
    """A single FUELHH actual generation value for one half-hour."""

    start_time: datetime
    publish_time: datetime | None
    generation_mw: float | None


@dataclass(frozen=True)
class Interval:
    """One matched (or partially missing) half-hour delivery interval."""

    start_time: datetime
    forecast_mw: float | None
    actual_mw: float | None
    forecast_publish_time: datetime | None

    @property
    def has_forecast(self) -> bool:
        return self.forecast_mw is not None

    @property
    def has_actual(self) -> bool:
        return self.actual_mw is not None

    @property
    def error_mw(self) -> float | None:
        """Forecast error (forecast - actual). Positive means over-forecast."""
        if self.forecast_mw is None or self.actual_mw is None:
            return None
        return self.forecast_mw - self.actual_mw

    def to_dict(self) -> dict:
        from app.timeutils import iso_utc

        return {
            "start_time": iso_utc(self.start_time),
            "forecast_mw": self.forecast_mw,
            "actual_mw": self.actual_mw,
            "error_mw": self.error_mw,
            "forecast_publish_time": iso_utc(self.forecast_publish_time),
        }


class ForecastIndex:
    """Forecast records indexed by target hour for O(log n) cutoff selection."""

    def __init__(self, records: Iterable[ForecastRecord]) -> None:
        deduped: dict[tuple[datetime, datetime], ForecastRecord] = {}
        duplicates = 0
        for record in records:
            key = (record.publish_time, record.start_time)
            if key in deduped:
                duplicates += 1
            deduped[key] = record  # last occurrence wins (explicit duplicate policy)

        self.records: list[ForecastRecord] = sorted(
            deduped.values(), key=lambda r: (r.publish_time, r.start_time)
        )
        self.duplicates_dropped = duplicates
        self.null_valued = sum(1 for r in self.records if r.generation_mw is None)

        by_target: dict[datetime, list[ForecastRecord]] = {}
        for record in self.records:
            by_target.setdefault(record.target_hour, []).append(record)
        self._by_target = {
            target: sorted(candidates, key=lambda r: r.publish_time)
            for target, candidates in by_target.items()
        }
        self._publish_times = {
            target: [c.publish_time for c in candidates]
            for target, candidates in self._by_target.items()
        }

    @classmethod
    def from_dicts(cls, rows: Iterable[Mapping]) -> "ForecastIndex":
        """Build an index from normalised ``forecasts.json`` records."""
        records = []
        for row in rows:
            publish = parse_utc(row.get("publish_time"))
            start = parse_utc(row.get("start_time"))
            if publish is None or start is None:
                continue
            raw_generation = row.get("generation_mw")
            records.append(
                ForecastRecord(
                    publish_time=publish,
                    start_time=start,
                    generation_mw=None if raw_generation is None else float(raw_generation),
                )
            )
        return cls(records)

    def select(self, target_hour: datetime, cutoff_utc: datetime) -> ForecastRecord | None:
        """Latest forecast for ``target_hour`` published at or before ``cutoff_utc``.

        Returns ``None`` when no eligible forecast exists (never a forecast
        published after the cutoff).
        """
        candidates = self._by_target.get(target_hour)
        if not candidates:
            return None
        position = bisect_right(self._publish_times[target_hour], cutoff_utc)
        if position == 0:
            return None
        chosen = candidates[position - 1]
        if chosen.generation_mw is None:
            return None
        return chosen

    def series_for_window(
        self, window_start: datetime, window_end: datetime
    ) -> list[tuple[datetime, list[ForecastRecord]]]:
        """All publications whose target times fall in ``[window_start, window_end)``.

        Returns ``(publish_time, records sorted by target)`` pairs ordered by
        publish time - the raw material for the forecast-evolution chart.
        """
        grouped: dict[datetime, list[ForecastRecord]] = {}
        for record in self.records:
            if window_start <= record.start_time < window_end:
                grouped.setdefault(record.publish_time, []).append(record)
        return [
            (publish, sorted(records, key=lambda r: r.start_time))
            for publish, records in sorted(grouped.items())
        ]


def build_intervals(
    index: ForecastIndex,
    actuals: Mapping[datetime, float | None],
    delivery_from: date,
    delivery_to: date,
    cutoff: CutoffRule,
) -> list[Interval]:
    """Match every half-hour interval in the delivery range to forecast/actual.

    ``actuals`` maps interval start (UTC) -> actual MW (``None`` allowed).
    Missing keys mean the actual is missing; missing forecasts are recorded as
    missing, never substituted with a post-cutoff value.
    """
    intervals: list[Interval] = []
    for start in delivery_slots(delivery_from, delivery_to):
        chosen = index.select(start.replace(minute=0, second=0, microsecond=0), cutoff.for_delivery(start))
        intervals.append(
            Interval(
                start_time=start,
                forecast_mw=chosen.generation_mw if chosen else None,
                actual_mw=actuals.get(start),
                forecast_publish_time=chosen.publish_time if chosen else None,
            )
        )
    return intervals


def actuals_from_dicts(rows: Iterable[Mapping]) -> dict[datetime, float | None]:
    """Map normalised ``actuals.json`` records to ``{interval_start: mw}``."""
    values: dict[datetime, float | None] = {}
    for row in rows:
        start = parse_utc(row.get("start_time"))
        if start is None:
            continue
        generation = row.get("generation_mw")
        values[start] = None if generation is None else float(generation)
    return values


def filter_intervals(
    intervals: Sequence[Interval],
    date_from: date | None = None,
    date_to: date | None = None,
    tz_name: str = "Europe/London",
) -> list[Interval]:
    """Filter intervals by inclusive **local delivery date** range."""
    if date_from is None and date_to is None:
        return list(intervals)
    selected: list[Interval] = []
    for interval in intervals:
        day = local_date(interval.start_time, tz_name)
        if date_from is not None and day < date_from:
            continue
        if date_to is not None and day > date_to:
            continue
        selected.append(interval)
    return selected
