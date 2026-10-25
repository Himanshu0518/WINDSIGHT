# syntax=docker/dockerfile:1
# WindSight API - serves the validated analysis dataset from memory on :8000.
#
#   docker build -t windsight-api backend
#   docker run --rm -p 8000:8000 windsight-api
#
# The dataset (actuals/forecasts/analysis JSON) is baked into the image, so
# the container serves real data immediately. To refresh it, run
# scripts/download_data.py on the host and mount the directory instead:
#
#   docker run --rm -p 8000:8000 -v "$(pwd)/backend/data:/app/data" windsight-api
#
# Allow your deployed frontend origin (required - the API only accepts
# configured origins):
#
#   -e CORS_ORIGINS="http://localhost:8080,https://your-domain"

FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

WORKDIR /app

# uv binary, matching the uv.lock that pins the dependency set.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Dependencies first: this layer stays cached until pyproject/uv.lock change.
# --no-install-project keeps the build free of any packaging step; the app
# runs straight from the source tree.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev --no-cache

# Application code + validated dataset (raw Elexon payloads are excluded
# via .dockerignore - only the normalised JSON ships).
COPY app ./app
COPY data ./data

ENV PATH="/app/.venv/bin:$PATH" \
    DATA_DIR=/app/data

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import sys, urllib.request; r = urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4); sys.exit(0 if r.status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
