# Run Toilet Map on your iPhone

## 1. Start the backend

On your Mac, from the repository root:

```sh
make backend-run
```

Keep that terminal running and use the same Wi-Fi network on your Mac and iPhone.
Allow Python/uvicorn through the Mac firewall if prompted. The server binds to
`0.0.0.0:8000` so the phone can reach it.

A fresh clone starts with sample data. Run `make backend-sync-data` to load the government dataset.
MOENV ingestion verifies TLS and may require a trusted `MOENV_CA_BUNDLE`; see
`backend/README.md` before refreshing the data.

## 2. Check the API address

Debug builds automatically select the API address for the destination:

| Destination | Default API |
| --- | --- |
| Physical iPhone | `http://your-mac.local:8000` |
| iOS simulator | `http://127.0.0.1:8000` |

On your iPhone, open `http://your-mac.local:8000/health` in Safari. Expect
`{"status":"ok"}`. This tests connectivity; the native app runs separately.

To find your Mac's hostname, run `scutil --get LocalHostName` and append
`.local`. Create `ios/ToiletMap/Configs/Local.xcconfig` (ignored by Git) to override
the device hostname:

```xcconfig
API_HOST[sdk=iphoneos*] = Your-Mac.local
```

The checked-in Debug config builds `API_BASE_URL` using an empty `$()` expansion
between the URL slashes so `//` is not interpreted as an xcconfig comment. Prefer
the `.local` hostname for local HTTP. Debug's `Info.Debug.plist` enables
`NSAllowsLocalNetworking`, without disabling ATS for all internet connections.
Do not copy a broad arbitrary-loads exception into Release.

For an existing HTTPS backend, override the full device URL instead:

```xcconfig
API_BASE_URL[sdk=iphoneos*] = https:/$()/your-api.example.com
```

On a physical iPhone, `127.0.0.1` points to the phone, not your Mac.

## 3. Open and sign the app

1. Open `ios/ToiletMap.xcodeproj` in Xcode.
2. Select the `ToiletMap` target, then **Signing & Capabilities**.
3. Keep **Automatically manage signing** enabled and select your Apple team.
   Add your Apple Account in Xcode settings if no team appears.
4. Change `com.example.ToiletMap` to a unique bundle identifier if signing asks.
5. Connect your unlocked iPhone by USB, trust the Mac, and choose the iPhone as
   the run destination for the `ToiletMap` scheme.
6. Enable **Settings → Privacy & Security → Developer Mode** on the iPhone if
   Xcode requests it; follow the restart and confirmation prompts.
7. Use the **Debug** configuration and press **Run** (Command-R).

Signing and trusting the device happen on your Mac/iPhone. An unsigned `.app`
from the command-line build cannot be installed directly.

## 4. Allow permissions and test

The project includes both required purpose strings:

- Location: find nearby public toilets. Choose **Allow While Using App** when
  prompted, or deny it to test map browsing without location.
- Local Network: connect to the development API on your Mac. Allow this when
  using the local backend.

If permission was denied, enable it in the app's iPhone Settings. Local network
privacy and ATS are separate checks; an HTTP exception does not grant local
network permission.

Suggested first pass:

1. Confirm toilets appear and Settings shows the expected development API URL.
2. Pan the map and change city, district, and facility filters.
3. Tap a pin to open its details and launch Apple Maps.
4. Open **List**, expand a result, and launch walking directions.
5. Stop the backend, trigger a reload, and confirm the error can be dismissed.

Known MVP limitations: no offline cache, at most 200 map results per request,
and open-now status is still based on ingested data rather than evaluated weekly
hours. Do not treat this test as verification of current opening times.

## Troubleshooting

- **No phone in Xcode:** check the cable, unlock/trust the phone, check Developer
  Mode, and open Xcode's Devices and Simulators window.
- **Signing error:** select your team and a unique bundle identifier.
- **Can't load toilets:** first check `/health` in iPhone Safari, then check the
  API shown in the app's Settings and its Local Network permission. Guest Wi-Fi,
  VPNs, or access-point isolation can prevent phone-to-Mac traffic.
- **Release build has no data:** Release intentionally uses a placeholder HTTPS
  endpoint in `Release.xcconfig`; device testing uses Debug.
- **Local API stops working away from home:** your phone must be able to reach
  the running Mac backend; cellular testing requires a reachable HTTPS backend.

## Command-line build check

```sh
make ios-build
```

This builds the iPhone binary without signing, using `ios/build/` for derived
data. It does not verify physical-device permissions, connectivity, or GPS.
