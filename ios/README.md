# Toilet Map for iPhone

Native SwiftUI app using MapKit, CoreLocation, and the FastAPI backend.
Requires Xcode with the iOS SDK and an iPhone running iOS 17 or newer.

Open `ios/ToiletMap.xcodeproj` and select the shared `ToiletMap` scheme.
The project includes every Swift source file; no packages or project generator
are required.

- **Debug / iPhone:** `http://your-mac.local:8000`
- **Debug / simulator:** `http://127.0.0.1:8000`
- **Release:** placeholder HTTPS URL; configure a deployed API before distributing.

See [DEVICE_TESTING_SETUP.md](DEVICE_TESTING_SETUP.md) for signing, permissions,
backend setup, and device troubleshooting.

Unsigned compilation check from the repository root:

```sh
make ios-build
```

This checks the device build but does not sign or install the app.

Map/list layout checks on iPhone:

- Tap the panel title/header to expand it; tap again for the full-height list.
  Drag the header between minimized, half-height, and expanded positions.
  Scroll inside the list; pan the exposed map. Filters should remain reachable.
- Tap a toilet marker: its expanded card should be highlighted and scrolled into
  view. Tap a counted marker: all records in that group should be available;
  **Show all** returns to the full result list. Zoom in to separate nearby markers.
- Tap the information area of a card: the map centers on it and the panel minimizes.
  Drag/scroll from a card instead: the map and selection must stay unchanged.
  **Open in Apple Maps** should still launch walking directions independently.
- With Traditional Chinese preferred, check distance labels use 公尺/公里.
  English uses m/km. Neither should show a straight-line qualifier.
- Check the distance order, hours/status, gender, diaper table, and accessibility
  rows. With location denied, distances explicitly use the map center instead.
- Apply filters that return no results, then clear them. Empty/loading/error
  messages belong inside the panel and must not cover the filters.
- Repeat with dark mode and larger text. Test an area with several toilet records
  sharing coordinates; they should remain accessible through the counted marker.

Automated model and request checks (no simulator/server required):

```sh
sh ios/Tests/check-request-coordination.sh
```

The marker count represents loaded government records. The existing API limit is
200 per viewport; zoom in to inspect a smaller area when that limit is reached.

The app now requests aggregated locations. See [aggregation pipeline](../docs/AGGREGATION.md)
for source preservation, matching rules, and the hospital-specific phone checks.
Restart the local backend if it is running without auto-reload, then rebuild the
app in Xcode. The first aggregated request publishes local groups automatically;
a government re-import is not required.
