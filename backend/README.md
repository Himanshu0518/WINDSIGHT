# WindSight backend

FastAPI service that serves the validated January 2026 wind forecast analysis
dataset. It never calls Elexon while serving a request - the dataset is loaded
once at startup and filtered in memory.

## Quick start

```bash
# 1. Download the dataset from the Elexon BMRS API (writes backend/data/)
uv run --project backend python scripts/download_data.py

# 2. Run the API (auto-reloads on change)
cd backend
uv run fastapi dev            # http://127.0.0.1:8000  (docs at /docs)

# 3. Run the tests
uv run pytest
```

Useful script flags:

```bash
uv run --project backend python scripts/download_data.py --sample   # print sample records
uv run --project backend python scripts/download_data.py --allow-partial  # record gaps instead of failing
```

## API endpoints

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Service health and dataset availability |
| `GET /api/overview?date=2026-01-15` | Forecast summary and headline metrics for a delivery date |
| `GET /api/forecasts?date=2026-01-15` | Half-hourly selected forecast vs. actual (48 intervals) |
| `GET /api/accuracy?from=2026-01-01&to=2026-01-31` | Aggregate + daily accuracy metrics |
| `GET /api/forecast-evolution?date=2026-01-15` | Every forecast publication for a delivery date |

Validation: invalid or out-of-range query parameters return `400` with a clear
message; a missing dataset returns `503` (never a stack trace). Interactive
docs are served by FastAPI at `/docs`.

## Project structure

```
backend/
├── app/
│   ├── main.py                  # FastAPI app factory, CORS, startup loading
│   ├── config.py                # environment-driven settings
│   ├── timeutils.py             # UTC normalisation, cutoff + DST helpers
│   ├── api/routes.py            # HTTP endpoints
│   ├── services/
│   │   ├── elexon_client.py     # BMRS client (7-day chunks, bounded retries)
│   │   ├── forecast_selection.py# cutoff rule, forecast selection, matching
│   │   ├── metrics.py           # MAE / RMSE / bias / MAPE + coverage
│   │   └── data_loader.py       # loads analysis.json into an in-memory store
│   └── schemas/forecast.py      # Pydantic response models
├── data/
│   ├── actuals.json             # normalised FUELHH wind actuals (generated)
│   ├── forecasts.json           # every WINDFOR forecast version (generated)
│   ├── analysis.json            # matched intervals served by the API (generated)
│   └── raw/                     # raw Elexon responses, saved before transform
├── tests/                       # forecast-selection and metrics unit tests
├── main.py                      # entry point for `fastapi dev` / `fastapi run`
└── pyproject.toml
```

## Forecast selection rule

For each delivery interval the cutoff is **10:00 Europe/London on the day
before delivery** (configurable via `DECISION_CUTOFF_*`), and the selected
forecast is the latest one published at or before that cutoff. If nothing was
published in time the interval is recorded as missing - a later forecast is
never used. Actuals are half-hourly (`FUELHH`), forecasts hourly (`WINDFOR`),
so the hourly value is broadcast to both half-hours it covers.

## Configuration

See `.env.example` in the repository root for every supported variable
(delivery period, cutoff rule, CORS origins, Elexon client settings).
