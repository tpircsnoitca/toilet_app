# Great Taipei Toilet Map - Test Cases Plan

## 1) Test Strategy

- Focus on MVP reliability for urgent use (find toilet fast, verify open status, navigate).
- Test from three layers:
  - Backend API correctness
  - iOS app behavior and UX
  - End-to-end real-world flows in Taipei/New Taipei
- Prioritize failures by impact:
  - `P0`: blocks core journey or gives dangerous/wrong guidance
  - `P1`: major UX degradation but workaround exists
  - `P2`: minor issues and polish

---

## 2) Environments

- Backend local/staging API
- iOS simulator (latest iOS)
- At least two physical iPhones:
  - newer device
  - older/slower device
- Network conditions:
  - stable Wi-Fi
  - unstable cellular
  - offline mode

---

## 3) Exit Criteria for MVP

- All `P0` test cases pass.
- At least 95% of `P1` test cases pass.
- No crash in 200 consecutive core-flow runs.
- Time from app open to first useful result:
  - <= 2s warm cache
  - <= 5s cold network path

---

## 4) Backend API Test Cases

## `BE-001` Health endpoint
- **Priority:** `P1`
- **Precondition:** API server running
- **Steps:** `GET /health`
- **Expected:** HTTP 200, body contains `status: ok`

## `BE-002` Meta endpoint freshness
- **Priority:** `P1`
- **Steps:** `GET /v1/meta`
- **Expected:** HTTP 200 with `lastSyncedAt`, coverage includes Taipei/New Taipei

## `BE-003` List toilets default
- **Priority:** `P0`
- **Steps:** `GET /v1/toilets`
- **Expected:** HTTP 200, valid JSON schema, `items` array and `total`

## `BE-004` Nearby requires lat/lng
- **Priority:** `P1`
- **Steps:** call `/v1/toilets/nearby` without lat/lng
- **Expected:** validation error (HTTP 422)

## `BE-005` Nearby distance ordering
- **Priority:** `P0`
- **Steps:** call nearby with known center, compare returned `distanceM`
- **Expected:** items sorted ascending by distance

## `BE-006` Radius boundary behavior
- **Priority:** `P0`
- **Steps:** test `radius_m` below min, above max, valid range
- **Expected:** invalid rejected, valid accepted

## `BE-007` City filter
- **Priority:** `P0`
- **Steps:** query `city=taipei`, then `city=new_taipei`
- **Expected:** results only from requested city

## `BE-008` District filter
- **Priority:** `P1`
- **Steps:** query district with known data
- **Expected:** all returned items match district

## `BE-009` Keyword filter
- **Priority:** `P1`
- **Steps:** search by known name fragment and address fragment
- **Expected:** only matching name/address records returned

## `BE-010` Feature filter diaper table
- **Priority:** `P1`
- **Steps:** query with `has_diaper_table=true/false`
- **Expected:** returned records match filter

## `BE-011` Toilet type filter
- **Priority:** `P1`
- **Steps:** query `toilet_type=accessible`
- **Expected:** every result contains accessible type

## `BE-012` Open-now filter
- **Priority:** `P0`
- **Steps:** query `open_now=true` at multiple times
- **Expected:** returned items satisfy current open status logic

## `BE-013` Detail endpoint existing id
- **Priority:** `P0`
- **Steps:** `GET /v1/toilets/{id}` for valid id
- **Expected:** HTTP 200 + full payload including opening hours

## `BE-014` Detail endpoint missing id
- **Priority:** `P1`
- **Steps:** `GET /v1/toilets/nonexistent`
- **Expected:** HTTP 404 with clear error message

## `BE-015` Schema compatibility contract
- **Priority:** `P0`
- **Steps:** run contract tests against iOS decoding models
- **Expected:** no required field mismatches

---

## 5) Open-Time Logic Test Cases

## `OT-001` 24-hour toilet
- **Priority:** `P0`
- **Expected:** `openNow=true` all day, label indicates 24h

## `OT-002` Normal daytime window
- **Priority:** `P0`
- **Expected:** open inside range, closed outside range

## `OT-003` Cross-midnight window
- **Priority:** `P0`
- **Case:** e.g., 22:00-05:00
- **Expected:** open at 23:30 and 02:00, closed at 12:00

## `OT-004` Missing/unknown schedule
- **Priority:** `P1`
- **Expected:** `openNow` nullable/unknown, fallback label shown

## `OT-005` Exact boundary times
- **Priority:** `P1`
- **Expected:** defined behavior at exact open and close minute

## `OT-006` Timezone safety
- **Priority:** `P0`
- **Expected:** calculations consistently use `Asia/Taipei`

---

## 6) iOS Functional Test Cases

## `IOS-001` First launch permission prompt
- **Priority:** `P0`
- **Steps:** fresh install -> open app
- **Expected:** location permission prompt appears with clear rationale

## `IOS-002` Permission denied fallback
- **Priority:** `P0`
- **Expected:** app remains usable (map/search/list still available)

## `IOS-003` Map renders pins
- **Priority:** `P0`
- **Expected:** map loads and shows toilets without crash

## `IOS-004` Nearby list navigation
- **Priority:** `P0`
- **Steps:** map -> list -> detail
- **Expected:** navigation stack works and data remains consistent

## `IOS-005` Detail content completeness
- **Priority:** `P1`
- **Expected:** name, address, open label, toilet types, diaper table render correctly

## `IOS-006` Apple Maps handoff
- **Priority:** `P0`
- **Expected:** correct destination opens in Apple Maps

## `IOS-007` Loading state visibility
- **Priority:** `P1`
- **Expected:** loading indicator appears/disappears correctly

## `IOS-008` Error state handling
- **Priority:** `P1`
- **Expected:** friendly error shown when API fails; no app freeze

## `IOS-009` Search/filter persistence
- **Priority:** `P1`
- **Expected:** selected filters are consistently applied across map/list

## `IOS-010` Background/resume behavior
- **Priority:** `P2`
- **Expected:** app resumes without losing current context unexpectedly

---

## 7) UX and Accessibility Test Cases

## `UX-001` One-hand reachability
- **Priority:** `P1`
- **Expected:** key actions reachable on large iPhone screens

## `UX-002` Dynamic type support
- **Priority:** `P1`
- **Expected:** larger text does not break core layouts

## `UX-003` VoiceOver labels
- **Priority:** `P1`
- **Expected:** essential controls are announced meaningfully

## `UX-004` Color contrast
- **Priority:** `P1`
- **Expected:** open/closed indicators remain readable in light/dark modes

---

## 8) Offline and Resilience Test Cases

## `RS-001` No network at launch
- **Priority:** `P0`
- **Expected:** cached data shown if available; clear stale-data hint

## `RS-002` Network drop mid-session
- **Priority:** `P1`
- **Expected:** graceful fallback; no crash; retry possible

## `RS-003` Slow API response
- **Priority:** `P1`
- **Expected:** loading UI remains responsive; timeout path handled

## `RS-004` Corrupt cache handling
- **Priority:** `P2`
- **Expected:** app recovers by clearing/re-fetching safely

---

## 9) Performance Test Cases

## `PF-001` Cold launch performance
- **Priority:** `P1`
- **Expected:** acceptable first frame and first result timings

## `PF-002` Warm launch performance
- **Priority:** `P1`
- **Expected:** map and cached pins appear quickly (target <= 2s)

## `PF-003` Map pan/zoom stress
- **Priority:** `P1`
- **Expected:** no severe frame drops or repeated duplicate fetch storms

## `PF-004` Large result set handling
- **Priority:** `P1`
- **Expected:** clustering/limits prevent UI lag and memory spikes

---

## 10) End-to-End Field Test Matrix (Great Taipei)

Run each scenario in both Taipei and New Taipei districts:

## `E2E-001` Urgent nearby find
- **Priority:** `P0`
- **Flow:** open app -> nearest open toilet -> navigate
- **Expected:** complete in <= 3 taps after app loads

## `E2E-002` Accessible toilet search
- **Priority:** `P0`
- **Flow:** apply accessible filter -> verify detail -> navigate

## `E2E-003` Diaper table scenario
- **Priority:** `P1`
- **Flow:** apply diaper table filter -> validate destination

## `E2E-004` Late-night availability
- **Priority:** `P0`
- **Flow:** search at late hours and verify open-now correctness

## `E2E-005` Location denied user
- **Priority:** `P1`
- **Flow:** deny location -> manual browse/search -> navigate

---

## 11) Automation Plan

- Backend automated:
  - Unit tests (parser, open-time logic)
  - API integration tests (filters, validation, schema contract)
- iOS automated:
  - Unit tests (repository, mapping)
  - UI tests for core flows
- Keep manual-only for:
  - field truth validation
  - navigation correctness in real streets
  - nuanced accessibility checks

---

## 12) Suggested Test Data Sets

- `Small`: 20 records for fast local tests
- `Medium`: 500 records for realistic UX tests
- `Edge`: records with missing hours, cross-midnight, unusual type combinations
- `GeoEdge`: boundary coordinates around Taipei/New Taipei border

---

## 13) Defect Triage Rules

- `P0` bug: fix before any beta distribution.
- `P1` bug: fix before release candidate unless accepted with explicit waiver.
- `P2` bug: backlog candidate if no user safety/core-flow impact.

---

## 14) Reporting Template (per test run)

- Build version:
- Environment/device:
- Test suite executed:
- Pass/fail counts by priority:
- New bugs created (IDs):
- Blockers:
- Go/No-go recommendation:
