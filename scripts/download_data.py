#!/usr/bin/env python3
"""Download WindSight data from the Elexon BMRS API and build the analysis dataset.

Data flow (generated artifacts, never hand-edited):

    Elexon BMRS API
      -> backend/data/raw/*.json          raw responses, saved before any transform
      -> backend/data/actuals.json         normalised FUELHH wind actuals (half-hourly)
      -> backend/data/forecasts.json       every WINDFOR forecast version (hourly)
      -> backend/data/analysis.json        matched intervals served by the API

Re-running the script rewrites every file from scratch, so repeated ingestion
never appends duplicates. Files are only written once the download has
succeeded - a failed or incomplete run never overwrites a good dataset unless
``--allow-partial`` is passed explicitly.

Usage (from the repository root):

    uv run --project backend python scripts/download_data.py              # full download
    uv run --project backend python scripts/download_data.py --sample     # print sample records
    uv run --project backend python scripts/download_data.py --allow-partial

Elexon constraints discovered during API exploration (see README):
  * FUELHH and WINDFOR accept date ranges of at most 7 days, inclusive.
  * FUELHH filters on settlement date; WINDFOR only filters on *publish* time,
    so a publish window wider than the delivery period is requested to keep
    every forecast version that was eligible at the decision cutoff.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import logging
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import Settings, get_settings  # noqa: E402
from app.services.elexon_client import (  # noqa: E402
    ElexonClient,
    ElexonError,
    iter_date_chunks,
    payload_rows,
)
from app.services.forecast_selection import (  # noqa: E402
    ForecastIndex,
    actuals_from_dicts,
    build_intervals,
)
from app.services.metrics import summarise  # noqa: E402
from app.timeutils import (  # noqa: E402
    delivery_slots,
    expected_interval_count,
    iso_utc,
    parse_utc,
)

logger = logging.getLogger("download_data")

SCHEMA_VERSION = 1
UTC = timezone.utc


# --- raw persistence ------------------------------------------------------
def write_json(path: Path, payload: Any) -> None:
    """Write JSON atomically (temp file + rename) and create parent dirs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=1, ensure_ascii=False)
        handle.write("\n")
    temporary.replace(path)


def fetch_payloads(
    client: ElexonClient,
    settings: Settings,
    forecast_from: date,
    forecast_to: date,
) -> tuple[list[dict], list[dict]]:
    """Download and persist every raw payload; return (actual rows, forecast rows)."""
    raw_dir = settings.raw_dir
    actual_rows: list[dict] = []
    forecast_rows: list[dict] = []

    for index, (start, end) in enumerate(
        iter_date_chunks(settings.delivery_from, settings.delivery_to), start=1
    ):
        payload = client.get_payload(
            "FUELHH",
            {
                "settlementDateFrom": start.isoformat(),
                "settlementDateTo": end.isoformat(),
                "fuelType": ["WIND"],
            },
        )
        rows = payload_rows(payload)
        name = f"fuelhh_{start.isoformat()}_{end.isoformat()}.json"
        write_json(raw_dir / name, payload)
        logger.info("FUELHH chunk %s: %s rows -> %s", index, len(rows), name)
        actual_rows.extend(rows)

    for index, (start, end) in enumerate(
        iter_date_chunks(forecast_from, forecast_to), start=1
    ):
        payload = client.get_payload(
            "WINDFOR",
            {
                "publishDateTimeFrom": f"{start.isoformat()}T00:00:00Z",
                "publishDateTimeTo": f"{end.isoformat()}T23:59:59Z",
            },
        )
        rows = payload_rows(payload)
        name = f"windfor_{start.isoformat()}_{end.isoformat()}.json"
        write_json(raw_dir / name, payload)
        logger.info("WINDFOR chunk %s: %s rows -> %s", index, len(rows), name)
        forecast_rows.extend(rows)

    return actual_rows, forecast_rows


# --- normalisation --------------------------------------------------------
def normalise_actuals(rows: list[dict]) -> tuple[list[dict], dict]:
    """Normalise raw FUELHH rows to UTC records, keeping one row per interval.

    Duplicate policy: when the same settlement period appears more than once,
    the record with the latest ``publishTime`` wins.
    """
    stats = {
        "raw_rows": len(rows),
        "non_wind_rows": 0,
        "duplicate_rows": 0,
        "null_generation_rows": 0,
        "unparsable_rows": 0,
    }
    best: dict[tuple[str, int], dict] = {}

    for row in rows:
        if row.get("fuelType") != "WIND":
            stats["non_wind_rows"] += 1
            continue
        start = parse_utc(row.get("startTime"))
        publish = parse_utc(row.get("publishTime"))
        settlement_date = row.get("settlementDate")
        settlement_period = row.get("settlementPeriod")
        if start is None or not settlement_date or settlement_period is None:
            stats["unparsable_rows"] += 1
            continue

        generation = row.get("generation")
        if generation is None:
            stats["null_generation_rows"] += 1

        key = (str(settlement_date), int(settlement_period))
        record = {
            "settlement_date": key[0],
            "settlement_period": key[1],
            "start_time": start,
            "publish_time": publish,
            "fuel_type": "WIND",
            "generation_mw": None if generation is None else float(generation),
        }
        existing = best.get(key)
        if existing is not None:
            stats["duplicate_rows"] += 1
            old_publish = existing.get("publish_time")
            if publish is not None and old_publish is not None and publish <= old_publish:
                continue  # keep the latest publication
        best[key] = record

    records = sorted(best.values(), key=lambda r: r["start_time"])
    serialised = [
        {
            "settlement_date": record["settlement_date"],
            "settlement_period": record["settlement_period"],
            "start_time": iso_utc(record["start_time"]),
            "publish_time": iso_utc(record["publish_time"]),
            "fuel_type": record["fuel_type"],
            "generation_mw": record["generation_mw"],
        }
        for record in records
    ]
    return serialised, stats


def normalise_forecasts(rows: list[dict]) -> tuple[list[dict], dict]:
    """Normalise raw WINDFOR rows; drop exact (publish, target) duplicates."""
    stats = {
        "raw_rows": len(rows),
        "duplicate_rows": 0,
        "null_generation_rows": 0,
        "unparsable_rows": 0,
    }
    best: dict[tuple[str, str], dict] = {}

    for row in rows:
        publish = parse_utc(row.get("publishTime"))
        start = parse_utc(row.get("startTime"))
        if publish is None or start is None:
            stats["unparsable_rows"] += 1
            continue
        generation = row.get("generation")
        if generation is None:
            stats["null_generation_rows"] += 1

        key = (iso_utc(publish) or "", iso_utc(start) or "")
        if key in best:
            stats["duplicate_rows"] += 1
        best[key] = {
            "publish_time": publish,
            "start_time": start,
            "generation_mw": None if generation is None else float(generation),
        }

    records = sorted(
        best.values(), key=lambda r: (r["publish_time"], r["start_time"])
    )
    serialised = [
        {
            "publish_time": iso_utc(record["publish_time"]),
            "start_time": iso_utc(record["start_time"]),
            "generation_mw": record["generation_mw"],
        }
        for record in records
    ]
    return serialised, stats


# --- validation -----------------------------------------------------------
def missing_actual_starts(
    actual_records: list[dict], delivery_from: date, delivery_to: date
) -> list[str]:
    """Delivery intervals (ISO-UTC) with no actual generation value."""
    present = {
        parse_utc(record["start_time"])
        for record in actual_records
        if record.get("generation_mw") is not None
    }
    return [
        iso_utc(slot) or ""
        for slot in delivery_slots(delivery_from, delivery_to)
        if slot not in present
    ]


# --- sample mode (Phase 1 exploration) ------------------------------------
def run_sample(settings: Settings, sample_date: date) -> int:
    """Fetch and print sample records from both datasets, then exit."""
    with ElexonClient(
        settings.elexon_base_url,
        timeout=settings.elexon_timeout_seconds,
        max_retries=settings.elexon_max_retries,
    ) as client:
        print(f"=== FUELHH sample ({sample_date.isoformat()}, fuelType=WIND) ===")
        payload = next(
            client.iter_fuelhh(sample_date, sample_date, fuel_types=("WIND",))
        )
        rows = payload_rows(payload)
        print(f"{len(rows)} records returned")
        for row in rows[:5]:
            print(json.dumps(row))

        publish_from = datetime.combine(
            sample_date - timedelta(days=1), datetime.min.time(), tzinfo=UTC
        )
        publish_to = datetime.combine(
            sample_date, datetime.max.time().replace(microsecond=0), tzinfo=UTC
        )
        print(f"\n=== WINDFOR sample (published {publish_from.date()}..{publish_to.date()}) ===")
        payload = next(client.iter_windfor(publish_from, publish_to))
        rows = payload_rows(payload)
        publications = sorted({row.get("publishTime") for row in rows})
        print(f"{len(rows)} records across {len(publications)} publications")
        for publish in publications:
            print(f"  publishTime={publish}")
        for row in rows[:5]:
            print(json.dumps(row))
    return 0


# --- main -----------------------------------------------------------------
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    defaults = get_settings()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", type=Path, default=defaults.data_dir)
    parser.add_argument("--delivery-from", type=date.fromisoformat, default=defaults.delivery_from)
    parser.add_argument("--delivery-to", type=date.fromisoformat, default=defaults.delivery_to)
    parser.add_argument(
        "--forecast-buffer-days",
        type=int,
        default=7,
        help="Extra days of forecast publications before the delivery period (default: 7).",
    )
    parser.add_argument(
        "--forecast-buffer-after",
        type=int,
        default=2,
        help="Extra days of forecast publications after the delivery period (default: 2).",
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Print sample records from both datasets (API exploration) and exit.",
    )
    parser.add_argument(
        "--sample-date",
        type=date.fromisoformat,
        default=None,
        help="Delivery date used by --sample (default: delivery period start).",
    )
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Write the dataset even when some delivery intervals have no actual data.",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    if args.delivery_to < args.delivery_from:
        parser.error("--delivery-to must be on or after --delivery-from")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    settings = dataclasses.replace(
        get_settings(),
        data_dir=args.data_dir,
        delivery_from=args.delivery_from,
        delivery_to=args.delivery_to,
    )

    if args.sample:
        return run_sample(settings, args.sample_date or settings.delivery_from)

    expected = expected_interval_count(settings.delivery_from, settings.delivery_to)
    forecast_from = settings.delivery_from - timedelta(days=args.forecast_buffer_days)
    forecast_to = settings.delivery_to + timedelta(days=args.forecast_buffer_after)
    print(
        f"Delivery period {settings.delivery_from}..{settings.delivery_to} "
        f"({expected} half-hour intervals)"
    )
    print(
        f"Forecast publications requested {forecast_from}..{forecast_to} "
        f"(cutoff: {settings.cutoff_description})"
    )

    try:
        with ElexonClient(
            settings.elexon_base_url,
            timeout=settings.elexon_timeout_seconds,
            max_retries=settings.elexon_max_retries,
        ) as client:
            raw_actuals, raw_forecasts = fetch_payloads(
                client, settings, forecast_from, forecast_to
            )
    except ElexonError as exc:
        print(f"ERROR: download failed: {exc}", file=sys.stderr)
        print("No analysis dataset was written (raw files kept for diagnosis).", file=sys.stderr)
        return 1

    actual_records, actual_stats = normalise_actuals(raw_actuals)
    forecast_records, forecast_stats = normalise_forecasts(raw_forecasts)
    print(f"Actuals:    {actual_stats}")
    print(f"Forecasts:  {forecast_stats}")

    missing_actuals = missing_actual_starts(
        actual_records, settings.delivery_from, settings.delivery_to
    )
    if missing_actuals:
        preview = ", ".join(missing_actuals[:5])
        print(
            f"WARNING: {len(missing_actuals)}/{expected} delivery intervals have no "
            f"actual generation ({preview}...)"
        )
        if not args.allow_partial:
            print(
                "ERROR: incomplete actuals; refusing to write a partial dataset. "
                "Re-run or pass --allow-partial to record the gaps explicitly.",
                file=sys.stderr,
            )
            return 1

    # --- match forecasts to actuals ------------------------------------
    index = ForecastIndex.from_dicts(forecast_records)
    intervals = build_intervals(
        index,
        actuals_from_dicts(actual_records),
        settings.delivery_from,
        settings.delivery_to,
        settings.cutoff_rule,
    )
    missing_forecasts = [iso_utc(i.start_time) for i in intervals if not i.has_forecast]
    if missing_forecasts:
        print(
            f"WARNING: {len(missing_forecasts)} intervals have no eligible forecast "
            f"(no publication at or before the cutoff); first: {missing_forecasts[0]}"
        )

    summary = summarise(intervals)
    print(f"Matched intervals: {summary.matched_intervals}/{expected} "
          f"(coverage {summary.coverage_percent}%)")
    print(
        f"MAE={summary.mae_mw} MW  RMSE={summary.rmse_mw} MW  "
        f"bias={summary.bias_mw} MW  MAPE={summary.mape_percent}%"
    )

    if summary.matched_intervals == 0:
        print("ERROR: no intervals could be matched; no dataset written.", file=sys.stderr)
        return 1

    # --- write artifacts ------------------------------------------------
    now = iso_utc(datetime.now(UTC))
    write_json(
        settings.actuals_path,
        {
            "generated_at": now,
            "dataset": "FUELHH",
            "source": settings.elexon_base_url,
            "fuel_type": "WIND",
            "record_count": len(actual_records),
            "stats": actual_stats,
            "records": actual_records,
        },
    )
    write_json(
        settings.forecasts_path,
        {
            "generated_at": now,
            "dataset": "WINDFOR",
            "source": settings.elexon_base_url,
            "record_count": len(forecast_records),
            "stats": forecast_stats,
            "records": forecast_records,
        },
    )
    write_json(
        settings.analysis_path,
        {
            "schema_version": SCHEMA_VERSION,
            "generated_at": now,
            "source": {
                "actuals_dataset": "Elexon BMRS FUELHH",
                "forecast_dataset": "Elexon BMRS WINDFOR",
                "api_base_url": settings.elexon_base_url,
            },
            "delivery": {
                "from": settings.delivery_from.isoformat(),
                "to": settings.delivery_to.isoformat(),
                "timezone": settings.decision_cutoff_timezone,
                "resolution_minutes": 30,
                "expected_intervals": expected,
            },
            "decision_cutoff": {
                "hour": settings.decision_cutoff_hour,
                "minute": settings.decision_cutoff_minute,
                "timezone": settings.decision_cutoff_timezone,
                "lead_days": settings.decision_cutoff_lead_days,
                "description": settings.cutoff_description,
            },
            "coverage": {
                "matched_intervals": summary.matched_intervals,
                "missing_actual_intervals": missing_actuals,
                "missing_forecast_intervals": missing_forecasts,
                "forecast_duplicates_dropped": index.duplicates_dropped,
            },
            "intervals": [interval.to_dict() for interval in intervals],
        },
    )

    print(f"Wrote {settings.actuals_path}")
    print(f"Wrote {settings.forecasts_path}")
    print(f"Wrote {settings.analysis_path}")
    if missing_actuals:
        print(f"NOTE: dataset is partial ({len(missing_actuals)} intervals lack actuals).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
