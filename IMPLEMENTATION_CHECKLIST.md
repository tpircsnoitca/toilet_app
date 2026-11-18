# Great Taipei Public Toilet Map - Implementation Checklist

## How to Use This Checklist

- Check items in order.
- Do not start later phases until earlier exit criteria pass.
- Keep focus on iPhone-first + Taipei/New Taipei only for v1.

---

## Week 0 - Project Setup and Discovery

### Goals

- Confirm source ingestion approach and finalize MVP boundaries.

### Tasks

- [ ] Create repo structure (`ios/`, `backend/`, `docs/`).
- [ ] Decide backend stack (FastAPI or Node) and DB.
- [ ] Inspect government site requests for structured endpoint.
- [ ] Capture sample source payloads or HTML fixtures.
- [ ] Draft source-to-schema mapping table.
- [ ] Confirm data reuse/attribution requirement text.
- [ ] Define Taipei + New Taipei district canonical names.

### Exit criteria

- [ ] You can fetch source data reliably by at least one method.
- [ ] Mapping table is documented and reviewed.
- [ ] MVP feature list is frozen.

---

## Week 1 - Backend Skeleton + Ingestion v0

### Goals

- Build first end-to-end data flow into database.

### Tasks

- [ ] Create backend service skeleton and `/health`.
- [ ] Create database schema for toilets and opening hours.
- [ ] Implement ingestion job:
  - [ ] fetch
  - [ ] parse
  - [ ] normalize
  - [ ] upsert
- [ ] Add ingestion run log table (status, duration, counts).
- [ ] Save raw snapshots for debugging.
- [ ] Seed DB with first Taipei/New Taipei dataset.

### Tests

- [ ] Parser unit tests for at least 10 varied records.
- [ ] Basic open-time parser tests (24h and normal ranges).

### Exit criteria

- [ ] Database contains valid records with coordinates and names.
- [ ] Ingestion can be rerun idempotently.

---

## Week 2 - API v1 for Map and Nearby

### Goals

- Deliver mobile-ready endpoints with filtering.

### Tasks

- [ ] Implement `GET /v1/meta`.
- [ ] Implement `GET /v1/toilets` with `bbox` and filters.
- [ ] Implement `GET /v1/toilets/nearby`.
- [ ] Implement `GET /v1/toilets/{id}`.
- [ ] Add pagination/limit guardrails.
- [ ] Add geospatial index for coordinate queries.
- [ ] Add timezone-safe open-now logic (`Asia/Taipei`).

### Tests

- [ ] API integration tests for each endpoint.
- [ ] Filter combination tests:
  - [ ] open now + accessible
  - [ ] diaper table + district
  - [ ] keyword + city
- [ ] Cross-midnight open-now tests.

### Exit criteria

- [ ] API can serve map viewport and nearby results under target latency.
- [ ] Open-now logic passes edge-case tests.

---

## Week 3 - iOS App Foundation

### Goals

- Build iPhone app skeleton and map rendering.

### Tasks

- [ ] Create SwiftUI app project and app-wide navigation.
- [ ] Implement location permission flow and fallback states.
- [ ] Build map screen with annotations.
- [ ] Build API client and DTO mapping.
- [ ] Implement viewport-based fetching (`bbox`).
- [ ] Add basic loading/empty/error states.

### Tests

- [ ] Unit tests for DTO mapping.
- [ ] Permission denied flow manual verification.
- [ ] Basic network failure handling test.

### Exit criteria

- [ ] User can open app and see toilets on map.
- [ ] Denied location still allows browsing by map/search.

---

## Week 4 - Filters, List, and Detail

### Goals

- Complete core user journey from discovery to decision.

### Tasks

- [ ] Add search bar (keyword).
- [ ] Add filter chips (open now, accessible, diaper table, type).
- [ ] Build nearby list sorted by distance.
- [ ] Build detail sheet with:
  - [ ] opening hours
  - [ ] facilities
  - [ ] management unit/address
- [ ] Add Apple Maps navigation handoff.

### Tests

- [ ] UI tests for filter toggles and result refresh.
- [ ] Detail rendering tests for null/missing fields.
- [ ] Manual test: open app -> navigate in <= 3 taps.

### Exit criteria

- [ ] Full MVP flow works end-to-end for both cities.

---

## Week 5 - Local Cache, Performance, and Stability

### Goals

- Improve perceived speed and reliability.

### Tasks

- [ ] Implement local cache for map/list/detail.
- [ ] Show data freshness timestamp.
- [ ] Add stale-data warning banner in offline mode.
- [ ] Add map clustering and fetch throttling.
- [ ] Optimize annotation updates to reduce jank.
- [ ] Tune API and app cold start.

### Tests

- [ ] Offline test with airplane mode.
- [ ] Performance profiling on at least one older iPhone.
- [ ] Memory leak and crash smoke tests.

### Exit criteria

- [ ] First useful map render <= 2s on warm launch.
- [ ] App remains usable with no network (cached data path).

---

## Week 6 - QA, Beta, and Launch Readiness

### Goals

- Prepare production-quality v1 for TestFlight/App Store.

### Tasks

- [ ] Execute field test matrix across districts in both cities.
- [ ] Verify opening-hours correctness for sampled locations.
- [ ] Add attribution and privacy policy screens.
- [ ] Finalize App Store metadata and screenshots.
- [ ] Fix high/medium priority bugs only.
- [ ] Freeze scope; defer extras to backlog.

### Exit criteria

- [ ] TestFlight build distributed to pilot users.
- [ ] No blocker bugs open.
- [ ] Launch checklist signed off.

---

## Cross-Cutting Definition of Done (Every Feature)

- [ ] Product behavior agreed and documented.
- [ ] Unit/integration tests updated.
- [ ] Error states handled (empty/loading/failure).
- [ ] Accessibility labels added for core controls.
- [ ] Logs/metrics added where useful.
- [ ] Reviewed on real device (not simulator only).

---

## Launch Checklist (Final Gate)

- [ ] Crash-free sessions target validated.
- [ ] API p95 latency target validated.
- [ ] Data sync alerts configured.
- [ ] Source attribution visible in app.
- [ ] Privacy text reviewed and published.
- [ ] Rollback plan documented (backend + app hotfix path).

---

## Backlog (After v1)

- [ ] User reports (closed/dirty/out-of-service)
- [ ] Favorites and recents
- [ ] Multi-language support (zh-Hant/en)
- [ ] Ranking by reliability/cleanliness signals
- [ ] Widget and Siri shortcut
