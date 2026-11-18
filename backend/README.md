# Backend (Starter)

## Run with uv

Python is pinned to 3.13 to match CI and the locked dependencies.

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Starter endpoints

- `GET /health`
- `GET /v1/meta`
- `GET /v1/toilets`
- `GET /v1/toilets/nearby`
- `GET /v1/toilets/{id}`
- `POST /v1/admin/sync`
- `GET /web` (Traditional Chinese toilet map for mobile and desktop browsers)

Open `http://localhost:8000/web/` locally. Location access requires HTTPS or a
browser-recognized local origin such as localhost. On a phone using the Mac's
plain HTTP network address, pan or zoom the map to browse without location.
The map uses Leaflet and OpenStreetMap tiles.

Useful filter params for list/nearby:
- `bbox=minLng,minLat,maxLng,maxLat` (list endpoint)
- `keyword`
- `open_now=true|false`
- `has_men_toilet=true|false`
- `has_women_toilet=true|false`
- `has_diaper_table=true|false`
- `gender=men&gender=women` matches either choice. The other supported choice
  is `gender_friendly`.
- `toilet_types=accessible` requires an accessible toilet.
- `aggregate=true` returns facility cards with original toilet records.

The list endpoint accepts `limit=1..200` (default `200`). Bounding boxes must
contain finite longitude/latitude values in `[-180, 180]` / `[-90, 90]`, with
minimums no greater than maximums. Nearby coordinates use the same ranges.

## Data storage (implemented)

- API now uses a SQLite database at `backend/data/toilets.db`.
- Tables are auto-created on app startup.
- Starter Taipei/New Taipei records are auto-seeded only when DB is empty.
- Override DB path with env var: `TOILET_DB_PATH=/path/to/toilets.db`.

## MOENV sync (implemented)

Sync command:

```bash
cd backend
uv run python -m app.ingestion.sync_moenv
```

What it does:
- fetches Taipei (`63000`) + New Taipei (`10001`) from MOENV web service
- normalizes toilet records and opening-hours fields
- upserts into `toilets` and `opening_hours`
- updates `app_meta.last_synced_at`

### Admin endpoint security

`POST /v1/admin/sync` is disabled (`503`) unless `TOILET_ADMIN_TOKEN` is set to
a nonblank secret in the backend environment. Generate a strong random token
(for example, `openssl rand -hex 32`) and store it in your secret manager.
Authorized requests must include `Authorization: Bearer <token>`; missing or
incorrect credentials return `401`. Use HTTPS outside local development and
never put this token in the web or iOS client. The local CLI sync command above
remains available without an HTTP token.

### Source TLS certificates

MOENV requests verify TLS certificates and hostnames. If the default trusted CA
store cannot validate the source certificate chain, configure `MOENV_CA_BUNDLE`
with the path to a trusted PEM CA bundle. Invalid certificates or bundles fail
the sync; there is no insecure fallback. Validate a replacement bundle's origin
before trusting it.

## Tests

From the project root:

```bash
uv run --project backend pytest backend/tests -q
node --test backend/tests/web_security.test.cjs
```

The web rendering regression test uses Node.js 22 or newer, with no npm packages.
Backend tests use temporary SQLite databases rather than the local dataset.

Test scope:
- Unit tests: `backend/tests/test_unit_toilet_service.py`
- Unit tests: `backend/tests/test_unit_moenv_ingestion.py`
- Integration tests: `backend/tests/test_integration_api.py`
- Smoke E2E flow: `backend/tests/test_smoke_e2e.py`

## Style and lint (ruff)

From the project root:

```bash
uv run --project backend ruff check backend
uv run --project backend ruff format backend
```
