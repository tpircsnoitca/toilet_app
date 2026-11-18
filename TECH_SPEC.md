# Great Taipei Public Toilet Map - Technical Spec (v1)

## 1. Scope and Non-Goals

### In scope (v1)

- iPhone-first iOS app for Taipei City + New Taipei City.
- Public toilet map, nearby search, filters, toilet detail, and navigation handoff.
- Open-now status from source open-time data.
- Backend ingestion and normalized read API.
- Local cache for faster startup and temporary offline viewing.

### Out of scope (v1)

- Android app.
- User-generated reports/moderation flow.
- Cross-city rollout beyond Taipei/New Taipei.
- Complex ranking/recommendation models.

---

## 2. System Architecture

1. Data Ingestion Worker
   - Runs on schedule (hourly recommended).
   - Fetches source data from government service.
   - Parses and normalizes records to internal schema.

2. API Service
   - Serves mobile-friendly endpoints.
   - Supports bounding box, nearby query, search, filters.
   - Returns compact JSON optimized for map rendering.

3. Database
   - Stores normalized toilets and opening-hours records.
   - Supports geospatial indexing.

4. iOS App
   - SwiftUI + MapKit + CoreLocation.
   - Fetches API data by viewport and filters.
   - Maintains local cache and open-now computation fallback.

---

## 3. Backend Design

### 3.1 Suggested stack

- API: FastAPI (Python) or Node.js (Express/Fastify)
- DB: PostgreSQL + PostGIS (preferred) or SQLite for prototype
- Scheduler: cron/Cloud Scheduler/GitHub Actions + worker runtime
- Hosting: Render/Fly.io/Railway/AWS (any equivalent PaaS is fine)

### 3.2 Data ingestion flow

1. Pull source records.
2. Validate required fields (`name`, `lat`, `lng`).
3. Convert district/city names into canonical forms.
4. Parse toilet type and feature tags.
5. Parse opening hours into normalized structure.
6. Upsert by stable source id (or deterministic hash fallback).
7. Write ingestion run metadata (count, failures, duration).

### 3.3 Data quality rules

- Ignore records outside Taipei/New Taipei bounds.
- Reject invalid coordinates or impossible time formats.
- Keep raw source snapshot for parser regression debugging.
- Mark uncertain fields as nullable; avoid fake defaults.

### 3.4 API endpoints (v1)

#### GET `/health`

- Basic service health.

#### GET `/v1/meta`

- Returns data freshness and supported filters.

Response example:

```json
{
  "lastSyncedAt": "2026-02-21T13:00:00Z",
  "coverage": ["Taipei", "New Taipei"],
  "version": "v1"
}
```

#### GET `/v1/toilets`

Query params:
- `bbox=minLng,minLat,maxLng,maxLat` (recommended for map)
- `city=taipei|new_taipei`
- `district=...`
- `keyword=...`
- `open_now=true|false`
- `has_diaper_table=true|false`
- `toilet_type=accessible|family|male|female|mixed|gender_friendly`
- `limit=200` (safe cap)

#### GET `/v1/toilets/nearby`

Query params:
- `lat`, `lng`, `radius_m` (default 1000, max 5000)
- same filters as `/v1/toilets`

#### GET `/v1/toilets/{id}`

- Full detail payload and normalized weekly hours.

### 3.5 Response model (map item)

```json
{
  "id": "tp_12345",
  "name": "Example Toilet",
  "city": "Taipei",
  "district": "Zhongzheng",
  "address": "No. 1, Example Rd.",
  "lat": 25.033,
  "lng": 121.5654,
  "toiletTypes": ["accessible", "family"],
  "hasDiaperTable": true,
  "openNow": true,
  "openLabel": "Open until 22:00",
  "distanceM": 320
}
```

### 3.6 Open-now logic

- Store weekly schedules in local timezone (`Asia/Taipei`).
- Handle these cases explicitly:
  - 24-hour opening
  - Cross-midnight windows (e.g., 22:00-05:00)
  - Missing/unknown hours
- If source quality is uncertain, return:
  - `openNow: null`
  - `openLabel: "Hours unavailable"`

---

## 4. iOS App Design

### 4.1 Stack

- Swift 5.10+
- SwiftUI
- MapKit
- CoreLocation
- URLSession
- Persistence: Core Data or SQLite wrapper (both acceptable)

### 4.2 App modules

- `App`: app entry, dependency setup.
- `Location`: permission and location updates.
- `Map`: annotations, clustering, viewport tracking.
- `SearchFilter`: keyword and chips.
- `ToiletDetail`: detail sheet and actions.
- `Data`: repository, DTO mapping, cache sync.

### 4.3 Key screens

1. Home Map
   - map pins + filter chips + locate button
2. Nearby List
   - sorted by distance, open status, tags
3. Detail Sheet
   - opening hours, facilities, navigate action
4. Settings/About
   - source attribution and last sync

### 4.4 State management

- Use MVVM with observable view models.
- Central filter state shared between map and list.
- Debounce search input (250-400ms).

### 4.5 Map data loading strategy

- On map move, query by `bbox` with throttle (300-500ms).
- Avoid overfetch by:
  - minimum zoom threshold for full map requests
  - max pins per response
  - clustering at lower zoom levels

### 4.6 Offline behavior

- Cache latest successful query results by region key.
- If network fails:
  - show cached pins
  - show "data may be outdated" banner
- Cache detail payload after first open.

### 4.7 Navigation handoff

- Use Apple Maps deep link or `MKMapItem` launch.
- Pass destination coordinate and name.

---

## 5. Security and Privacy

- Do not collect precise location unless needed for nearby feature.
- Keep location processing on-device where possible.
- No account required in v1.
- Add clear usage text for location permission.
- Publish privacy policy with explicit no-sale/no-tracking statement (if true).

---

## 6. Observability and Operations

### Backend metrics

- Ingestion success/failure count
- Parse error count
- API latency p50/p95
- API error rates by endpoint

### iOS telemetry (minimal)

- App startup time
- Query success/failure
- Time to first result
- Crash reports (via standard crash tooling)

---

## 7. Testing Strategy

### Backend

- Parser tests with fixed source fixtures
- Open-now logic unit tests (24h, cross-midnight, unknown)
- API integration tests for filters and bbox

### iOS

- Unit tests for filter/state logic
- Snapshot/UI tests for key screens
- Permission-flow tests for location denied/allowed
- Manual field tests in at least 10 districts across both cities

---

## 8. Performance Targets

- Map first meaningful render: <= 2.0s (warm cache)
- Nearby query API p95: <= 500ms
- Detail open latency: <= 500ms (cached <= 200ms)
- iPhone memory steady-state target: < 250MB

---

## 9. Release Plan

### Environments

- `dev`: rapid iteration and parser testing
- `staging`: TestFlight backend
- `prod`: App Store release backend

### CI/CD

- Backend: test -> build -> deploy on main
- iOS: test -> archive -> TestFlight
- Ingestion job: scheduled with alerting on failure

---

## 10. Open Decisions (Resolve Early)

1. Is there a stable structured source endpoint behind the site?
2. What is the final storage choice for local cache (Core Data vs SQLite wrapper)?
3. What telemetry tool will be used (or none in v1)?
4. What is acceptable sync frequency vs source update behavior?

---

## 11. Initial Folder Structure Suggestion

```text
toilet_app/
  backend/
    app/
      api/
      core/
      ingestion/
      models/
      tests/
  ios/
    ToiletMap/
      App/
      Features/
        Map/
        List/
        Detail/
        Settings/
      Services/
      Data/
      Resources/
  docs/
    PROJECT_PLAN.md
    TECH_SPEC.md
    IMPLEMENTATION_CHECKLIST.md
```
