"""Smoke-test a release against its validated SQLite sync timestamp."""

import json
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

origin, expected_sync = sys.argv[1:]


def request(path, method="GET"):
    return urlopen(Request(origin + path, method=method), timeout=45)


for attempt in range(6):
    try:
        with request("/health") as response:
            assert json.load(response)["status"] == "ok"
        break
    except (URLError, ConnectionError, TimeoutError):
        if attempt == 5:
            raise
        time.sleep(3)

with request("/v1/meta") as response:
    assert json.load(response)["lastSyncedAt"] == expected_sync
with request("/web/") as response:
    assert response.status == 200 and "<html" in response.read().decode().lower()
with request(
    "/v1/toilets/nearby?lat=25.033&lng=121.5654&radius_m=1000&aggregate=true"
) as response:
    nearby = json.load(response)
    assert nearby["total"] > 0 and all(
        card.get("sourceRecords") for card in nearby["items"]
    )
try:
    request("/v1/admin/sync", method="POST")
except HTTPError as error:
    assert error.code == 503
else:
    raise AssertionError("Admin sync is enabled")
print(f"Smoke tests passed for {origin}: {nearby['total']} nearby facility cards")
