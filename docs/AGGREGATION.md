# Toilet aggregation pipeline

The iOS client requests `aggregate=true`. Raw APIs remain available without this
parameter. Aggregated items embed `sourceRecords`, `symbolSources` (symbol to
original record IDs), `matchingSourceIds`, `sourceCount`, and `aggregationVersion`.
The detail endpoint still addresses original government IDs; display group IDs
are not source IDs. iOS reads group details from the embedded records.

## Preservation and publication

- Every subsequent government fetch archives its complete decoded response before
  normalization. `source_imports` records fetch occurrences; identical payload
  content shares an immutable `source_snapshots` row. SQL triggers prohibit
  modifying/deleting snapshots.
- Existing data is archived as `normalized_database`, including all toilets and
  weekly opening hours. This cannot reconstruct previously discarded source fields.
- Source records retain their original IDs, names, addresses, and coordinates.
  Aggregation never deletes or rewrites them. The API no longer strips floors or
  gender from original names.
- `aggregation_versions` stores immutable-by-convention group membership, rule
  version, and a review report. `app_meta.aggregation_version` identifies the
  active generated version. Old versions and input snapshots are retained for
  audit/recovery; there is no automatic destructive database rollback.
- Publication runs after successful sync or lazily on the first aggregated API
  request. Source-table revision triggers invalidate derived membership when
  toilets/hours change; open-now values are always computed at request time.
- All source IDs must appear exactly once in the published membership. Group IDs
  are derived from matching keys, independent of API order and filters.

## Matching and display rules (version 3)

Candidates match by city, normalized address, and facility name. For addresses
with a house number, the name key drops trailing floor, building and toilet type
labels. Department names and room codes still distinguish records. Exact name
matching remains available for locality-only addresses. Missing names or
addresses stay separate.

Card titles use the facility name even for single-record cards. Those cards
show floor and building separately when available. Source records retain their
complete names.

The 150-metre maximum pairwise spread holds unreviewed candidates apart and
writes a `coordinate_spread` entry. The reviewed hospital prefix still groups
聯合醫院和平婦幼院區（婦幼）. Reviewed mappings also group 大全聯土城店 and 漁夫巿集
across coordinate conflicts, recording those conflicts in the same report. The
market mapping accepts the specific truncated address seen in its source data.

The representative point is an actual source coordinate. For a reviewed group
with conflicting coordinates, it is selected by most neighbours within 150
metres, then lowest sum of distances, then source ID. Other groups use the
first source ID. Viewport/radius queries use that point;
child records remain complete even across a viewport boundary. Limits apply after
grouping. The 200-result viewport limit remains in place.

## Summaries and filtering

Known male/female flags, accessible/family/gender-friendly types, and diaper-table
flags produce symbols with supporting source IDs. Unspecified gender remains
unknown and does not satisfy gender filters. Family does not imply a diaper table.

Every active filter must match the same original toilet. A selected group retains
all children and separately identifies matching children. An open regular toilet
plus an unknown/closed accessible toilet cannot satisfy open-now + accessible.

Any known-open child means some toilets are open. Closed requires every child to
be known closed; otherwise status is unknown. Today's shared hours appear only
when all children agree; otherwise the card says hours vary. Weekly schedule and
facility differences are also recorded in the publication review report.

## Verification

Run `uv run --no-sync --project backend pytest backend/tests -q` and
`sh ios/Tests/check-request-coordination.sh` from the repository root.
The Swift checks decode a real aggregated hospital response fixture.

On iPhone, inspect the hospital at 福州街12號: one card should show both gender
symbols and Family, without inventing a diaper table or accessibility. Open
“View details” to check the original names, including 第二棟 floors.
Scroll cards without moving the map; tap a card to focus its location; navigation
and the locations button should operate independently. Test accessible + gender
and open-now combinations, empty results, and symbols with larger text/dark mode.
