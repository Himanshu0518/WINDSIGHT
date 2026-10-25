"""Timestamp helpers shared across the WindSight backend.

All timestamps are normalised to timezone-aware UTC datetimes and serialised
with a trailing ``Z`` (for example ``2026-01-15T10:00:00Z``). Delivery dates
are interpreted in a configurable IANA timezone (``Europe/London`` by default)
so daylight-saving changes are handled by the standard library.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Iterator
from zoneinfo import ZoneInfo

UTC = timezone.utc

_ZONE_CACHE: dict[str, ZoneInfo] = {}


def zone(name: str) -> ZoneInfo:
    """Return a cached ``ZoneInfo`` for ``name`` (raises KeyError if unknown)."""
    cached = _ZONE_CACHE.get(name)
    if cached is None:
        cached = ZoneInfo(name)
        _ZONE_CACHE[name] = cached
    return cached


def parse_utc(value: str | datetime | None) -> datetime | None:
    """Parse an ISO-8601 timestamp into a UTC datetime.

    Naive values are assumed to already be UTC. Returns ``None`` for empty
    input so callers can treat missing timestamps as missing data rather than
    crashing.
    """
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).strip())
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def iso_utc(value: datetime | None) -> str | None:
    """Serialise a datetime as ``YYYY-MM-DDTHH:MM:SSZ`` (or ``None``)."""
    if value is None:
        return None
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def local_date(value: datetime, tz_name: str) -> date:
    """Calendar date of ``value`` in the given timezone."""
    return value.astimezone(zone(tz_name)).date()


def local_cutoff(
    moment_utc: datetime,
    *,
    hour: int,
    minute: int,
    tz_name: str,
    lead_days: int,
) -> datetime:
    """Decision cutoff (UTC) that applies to the delivery day of ``moment_utc``.

    The cutoff is ``hour:minute`` local time on the day ``lead_days`` before
    the delivery day. The local wall-clock date is used for the day arithmetic
    and the resulting local datetime is converted to UTC, so the rule stays
    correct across daylight-saving transitions.
    """
    local_moment = moment_utc.astimezone(zone(tz_name))
    decision_day = (local_moment - timedelta(days=lead_days)).date()
    local_cutoff_dt = datetime.combine(
        decision_day, time(hour, minute), tzinfo=zone(tz_name)
    )
    return local_cutoff_dt.astimezone(UTC)


def cutoff_description(hour: int, minute: int, tz_name: str, lead_days: int) -> str:
    """Human-readable description of a cutoff rule."""
    day_word = "the day before delivery" if lead_days == 1 else f"{lead_days} days before delivery"
    return f"{hour:02d}:{minute:02d} {tz_name}, {day_word}"


def delivery_slots(delivery_from: date, delivery_to: date) -> Iterator[datetime]:
    """Yield every half-hour delivery interval (UTC) in an inclusive date range.

    ``delivery_from == delivery_to == 2026-01-15`` yields the 48 intervals of
    that day, starting at ``2026-01-15T00:00:00Z``.
    """
    if delivery_to < delivery_from:
        raise ValueError(
            f"delivery_to ({delivery_to}) must not be before delivery_from ({delivery_from})"
        )
    current = datetime.combine(delivery_from, time.min, tzinfo=UTC)
    end = datetime.combine(delivery_to, time.min, tzinfo=UTC) + timedelta(days=1)
    while current < end:
        yield current
        current += timedelta(minutes=30)


def expected_interval_count(delivery_from: date, delivery_to: date) -> int:
    """Number of half-hour intervals in an inclusive delivery date range."""
    return ((delivery_to - delivery_from).days + 1) * 48
