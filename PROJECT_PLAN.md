# Great Taipei Public Toilet Map (iPhone-First) - Project Plan

## 1) Project Goal

Build an iOS app (iPhone-first) that helps people quickly find public toilets in **Taipei City** and **New Taipei City**, with emphasis on:

- Nearby toilet discovery on map
- Open-time visibility (open now / opening hours)
- Fast navigation from current location
- Useful filters (accessible toilet, baby changing table, etc.)

Data source (official government site):
- https://esms.moenv.gov.tw/eco/toilet/FindToilet.aspx?openExternalBrowser=1

---

## 2) Product Scope (MVP First)

### MVP (v1)

1. Show toilets on map for Taipei + New Taipei.
2. Current location + "near me" sorting.
3. Toilet detail card:
   - Name
   - Address / management unit (if available)
   - Toilet type
   - Open hours
   - Diaper table availability
4. "Open now" indicator and open-time filtering.
5. Basic search (keyword + district).
6. Launch Apple Maps for turn-by-turn navigation.
7. Offline cache of last synced data (read-only) for basic usability.

### Post-MVP (v1.1+)

- User reports (closed / dirty / unavailable)
- Favorites and recent history
- Smart ranking (distance + cleanliness confidence + reliability)
- Widget / Siri shortcut
- Multi-language UI (Traditional Chinese + English)

---

## 3) Target Users and Key Scenarios

### Primary users

- Commuters and tourists in Great Taipei
- Parents with children (need diaper table)
- Elderly or accessibility-needs users
- Drivers, delivery staff, cyclists

### Top scenarios

1. "I need a toilet in 3 minutes near me."
2. "I only want toilets open right now."
3. "I need an accessible toilet / family toilet."
4. "Take me there now."

---

## 4) Data Strategy

The official page clearly contains searchable records and map/location features. For production quality, plan data ingestion in this order:

### Step A - Check for structured endpoint (preferred)

- Inspect network calls from the government page.
- Determine whether there is a JSON/XML endpoint behind the search UI.
- If available and stable, use this endpoint directly.

### Step B - Controlled scraper fallback

If no public API exists:

- Build a scheduled extractor to collect records from the site.
- Normalize to your own schema.
- Store timestamped snapshots.
- Add retries + change detection for HTML structure updates.

### Step C - Data governance

- Confirm usage policy / terms for public data reuse.
- Keep attribution in app settings/about.
- Maintain sync logs and data freshness indicators.

---

## 5) Suggested Tech Stack (iOS-First)

### iOS app

- **Swift + SwiftUI**
- **MapKit** for map rendering and annotations
- **CoreLocation** for user location and permission flow
- **URLSession** for API fetch
- **SQLite / Core Data** for local cache

### Backend (recommended, even for mobile-first)

- Lightweight service (e.g., FastAPI/Node) to:
  - Pull/clean source data
  - Provide stable mobile-friendly API
  - Handle sync, deduplication, validation

### Why a backend is recommended

- Decouples iOS app from source-site HTML changes
- Better performance (pre-processed filters and indexing)
- Easier future expansion (analytics, reports, ranking)

---

## 6) High-Level System Design

1. **Ingestion job** (hourly/daily) fetches source data.
2. **Normalizer** converts source fields into unified schema.
3. **Database** stores toilets, hours, tags, geolocation.
4. **Mobile API** serves:
   - Bounding-box map query
   - Nearby query
   - Filter query (open now, accessible, diaper table, type)
5. **iOS app** displays map/list + detail + navigation.
6. **Local cache** supports quick load + temporary offline mode.

---

## 7) Data Model (Initial)

### Toilet

- `id` (string)
- `name`
- `city` (Taipei / New Taipei)
- `district`
- `address`
- `lat`, `lng`
- `toilet_types` (male/female/family/accessible/mixed/gender-friendly)
- `has_diaper_table` (bool)
- `floor` (optional)
- `management_unit` (optional)
- `rating_level` (if available from source)
- `updated_at`

### OpeningHours

- `toilet_id`
- `day_of_week` (0-6)
- `open_time`
- `close_time`
- `is_24h`
- `notes` (optional)

---

## 8) UX Plan (iPhone-First)

### Core screens

1. **Map Home**
   - Search bar
   - Filter chips (Open now, Accessible, Diaper table)
   - Floating "locate me" button
2. **List View**
   - Distance + open status + key tags
3. **Detail Sheet**
   - Full info + open hours + "Navigate"
4. **Settings/About**
   - Data attribution and last sync time

### Interaction priorities

- One-thumb usage
- Fast first paint (cached markers)
- Minimal taps from open app to navigation

---

## 9) Delivery Plan and Milestones

### Phase 0 - Discovery (3-5 days)

- Validate source endpoint availability
- Confirm legal/data usage constraints
- Define exact city boundary and district mapping
- Finalize MVP scope

**Exit criteria:** Data pipeline approach selected (API or scraper), legal confidence documented.

### Phase 1 - Data Pipeline + API (1-2 weeks)

- Build ingestion + normalization
- Store in DB and expose read API
- Add tests for parser and transformation
- Set up scheduled sync and monitoring

**Exit criteria:** Reliable API serving Taipei + New Taipei toilets with filters.

### Phase 2 - iOS MVP App (2-3 weeks)

- Map + location permission flow
- Marker clustering and detail sheet
- Search and filtering
- Open-now logic
- Apple Maps handoff
- Local cache

**Exit criteria:** Internal beta build usable end-to-end.

### Phase 3 - QA + Beta (1 week)

- Field-test in multiple districts
- Validate open-time edge cases (cross-midnight, 24h)
- Performance optimization on older iPhones
- Crash and permission-flow hardening

**Exit criteria:** TestFlight-ready beta.

### Phase 4 - Launch Prep (3-5 days)

- App Store metadata and screenshots
- Privacy policy and attribution page
- Final bug fixes

**Exit criteria:** v1 release candidate.

---

## 10) Risks and Mitigations

1. **Source format changes**
   - Mitigation: backend abstraction + parser tests + alerts
2. **No stable public API**
   - Mitigation: controlled scraper + cache + low-frequency sync
3. **Opening-hours inconsistencies**
   - Mitigation: normalize rules + show "data may vary" flag
4. **Location permission denial**
   - Mitigation: support manual district/keyword search
5. **Map performance with many markers**
   - Mitigation: clustering + viewport-based query

---

## 11) Success Metrics (MVP)

- Time to first useful result: < 2 seconds (with cache)
- 90%+ of searches return at least one nearby result in covered area
- Crash-free sessions > 99.5%
- Median taps from app open to navigation <= 3

---

## 12) Immediate Next Actions

1. Inspect the government page network calls for structured data endpoint.
2. Draft a field mapping table from source fields to app schema.
3. Spin up minimal backend API skeleton (`/toilets`, `/toilets/nearby`).
4. Scaffold SwiftUI iOS app with MapKit + location permission flow.
5. Create 10 real-world test routes across Taipei and New Taipei for QA.

---

## 13) Notes for This Project

- Keep focus on **Taipei + New Taipei only** in v1 to guarantee quality and speed.
- Optimize for emergency use: rapid location, open-now clarity, and quick navigation.
- Build data layer as a long-term asset so future city expansion is easy.
