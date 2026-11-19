FROM python:3.15-slim@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928 AS python-base

# The pinned image predates Debian's zlib security update for CVE-2026-85091.
RUN apt-get update \
    && apt-get install -y --no-install-recommends --only-upgrade zlib1g \
    && dpkg --compare-versions "$(dpkg-query -W -f='${Version}' zlib1g)" ge '1:1.3.dfsg+really1.3.1-1+deb13u1' \
    && rm -rf /var/lib/apt/lists/*

FROM python-base AS dependencies
COPY --from=ghcr.io/astral-sh/uv:0.13.7@sha256:96f40d3904aad8d0bd010539001d36c8e2188b981e1334471a90c4a1d93bb490 /uv /usr/local/bin/uv
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
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port \"${PORT:-8080}\" --no-access-log"]
