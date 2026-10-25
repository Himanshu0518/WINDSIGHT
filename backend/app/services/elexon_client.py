"""HTTP client for the Elexon BMRS Insights API.

Public base URL: ``https://data.elexon.co.uk/bmrs/api/v1``

WindSight uses two raw BMRS datasets:

* ``FUELHH`` - half-hourly generation outturn by fuel type (actuals, MW).
  Filterable with ``settlementDateFrom``/``settlementDateTo``/``fuelType``.
* ``WINDFOR`` - wind generation forecast (MW), published several times a day.
  Only filterable by **publish** time (``publishDateTimeFrom``/``To``), so the
  download script must request a publish window wide enough to cover every
  forecast that was eligible for the delivery period.

Both endpoints reject any date range longer than 7 days inclusive, so every
request is automatically split into 7-day chunks. Payloads are returned
exactly as received so callers can persist the raw response before
transforming it.
"""

from __future__ import annotations

import logging
import time
from datetime import date, datetime, time as dt_time, timedelta, timezone
from typing import Any, Iterator, Mapping, Sequence

import httpx

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://data.elexon.co.uk/bmrs/api/v1"

# Elexon returns HTTP 400 when settlementDate/publishDateTime windows exceed 7 days.
MAX_RANGE_DAYS = 7

RETRYABLE_STATUS = {429, 500, 502, 503, 504}
RETRYABLE_EXCEPTIONS = (httpx.TransportError, httpx.TimeoutException)

UTC = timezone.utc


class ElexonError(RuntimeError):
    """Elexon returned an error we cannot recover from (4xx or malformed payload)."""


class ElexonTransientError(ElexonError):
    """Elexon kept failing after the configured number of retries."""


def iter_date_chunks(start: date, end: date) -> Iterator[tuple[date, date]]:
    """Yield inclusive ``(chunk_start, chunk_end)`` windows of <= 7 days."""
    if end < start:
        raise ValueError(f"end date {end} is before start date {start}")
    current = start
    while current <= end:
        chunk_end = min(current + timedelta(days=MAX_RANGE_DAYS - 1), end)
        yield current, chunk_end
        current = chunk_end + timedelta(days=1)


def _problem_detail(response: httpx.Response) -> str:
    """Best-effort message from an RFC 7807 problem+json error body."""
    try:
        body = response.json()
    except ValueError:
        return response.text[:300]
    if isinstance(body, dict):
        errors = body.get("errors")
        if isinstance(errors, dict):
            parts = [f"{key}: {', '.join(map(str, vals))}" for key, vals in errors.items()]
            if parts:
                return "; ".join(parts)
        for key in ("detail", "title", "message"):
            if body.get(key):
                return str(body[key])
    return str(body)[:300]


class ElexonClient:
    """Small, dependency-light client with bounded retries and explicit timeouts."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        *,
        timeout: float = 30.0,
        max_retries: int = 3,
        backoff_seconds: float = 1.5,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self._client = httpx.Client(
            timeout=timeout,
            transport=transport,
            headers={"User-Agent": "windsight/1.0 (windSight data pipeline)"},
        )

    # --- lifecycle -----------------------------------------------------
    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "ElexonClient":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # --- core request --------------------------------------------------
    def get_payload(self, dataset: str, params: Mapping[str, Any]) -> dict:
        """GET ``/datasets/{dataset}`` and return the raw JSON payload.

        Retries timeouts, connection errors, 429 and 5xx responses with a
        bounded exponential backoff. Non-retryable failures raise
        ``ElexonError`` without ever returning a partial payload.
        """
        url = f"{self.base_url}/datasets/{dataset}"
        attempts = self.max_retries + 1
        last_error: BaseException | None = None

        for attempt in range(attempts):
            if attempt:
                delay = self.backoff_seconds * (2 ** (attempt - 1))
                logger.warning(
                    "Retrying %s in %.1fs (attempt %s/%s) after %s",
                    dataset, delay, attempt + 1, attempts, last_error,
                )
                time.sleep(delay)
            try:
                response = self._client.get(url, params=dict(params))
            except RETRYABLE_EXCEPTIONS as exc:
                last_error = exc
                continue

            if response.status_code in RETRYABLE_STATUS:
                last_error = ElexonTransientError(
                    f"{dataset} returned HTTP {response.status_code}"
                )
                continue

            if response.status_code != 200:
                raise ElexonError(
                    f"{dataset} request failed with HTTP {response.status_code}: "
                    f"{_problem_detail(response)}"
                )

            try:
                payload = response.json()
            except ValueError as exc:
                raise ElexonError(f"{dataset} returned invalid JSON") from exc

            if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
                raise ElexonError(
                    f"Unexpected {dataset} payload shape (keys="
                    f"{sorted(payload) if isinstance(payload, dict) else type(payload).__name__})"
                )
            return payload

        raise ElexonTransientError(
            f"{dataset} request failed after {attempts} attempts: {last_error}"
        )

    # --- dataset helpers -----------------------------------------------
    def iter_fuelhh(
        self,
        date_from: date,
        date_to: date,
        fuel_types: Sequence[str] = ("WIND",),
    ) -> Iterator[dict]:
        """Yield raw FUELHH payloads covering ``date_from``..``date_to`` (inclusive)."""
        for chunk_start, chunk_end in iter_date_chunks(date_from, date_to):
            params: dict[str, Any] = {
                "settlementDateFrom": chunk_start.isoformat(),
                "settlementDateTo": chunk_end.isoformat(),
            }
            if fuel_types:
                params["fuelType"] = list(fuel_types)
            logger.info("FUELHH %s .. %s", chunk_start, chunk_end)
            yield self.get_payload("FUELHH", params)

    def iter_windfor(
        self, publish_from: datetime, publish_to: datetime
    ) -> Iterator[dict]:
        """Yield raw WINDFOR payloads for a publish-time window.

        Windows are chunked by calendar day (7 days per request) and widened
        to whole days, which only ever adds earlier publications - never
        removes forecast versions needed for selection.
        """
        for chunk_start, chunk_end in iter_date_chunks(
            publish_from.date(), publish_to.date()
        ):
            window_from = datetime.combine(chunk_start, dt_time.min, tzinfo=UTC)
            window_to = datetime.combine(chunk_end, dt_time.max, tzinfo=UTC)
            params = {
                "publishDateTimeFrom": window_from.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "publishDateTimeTo": window_to.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
            logger.info("WINDFOR publish window %s .. %s", chunk_start, chunk_end)
            yield self.get_payload("WINDFOR", params)


def payload_rows(payload: Mapping[str, Any]) -> list[dict]:
    """Extract the record list from a raw dataset payload."""
    rows = payload.get("data", [])
    return [row for row in rows if isinstance(row, dict)]
