FROM python:3.13-slim AS python-base

FROM python-base AS dependencies
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /usr/local/bin/uv
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --locked --no-dev --no-install-project --no-managed-python --no-cache

FROM python-base
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TOILET_DB_PATH=/var/lib/toilet-map/toilets.sqlite3
WORKDIR /app
COPY --from=dependencies /app/.venv ./.venv
COPY backend/app/ ./app/
COPY backend/web/ ./web/

RUN install -d -m 0700 -o 10001 -g 10001 /var/lib/toilet-map
COPY --chown=10001:10001 --chmod=0600 checkpoint.sqlite3 /var/lib/toilet-map/toilets.sqlite3
USER 10001:10001
RUN test -s "$TOILET_DB_PATH"

EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port \"${PORT:-8080}\""]
