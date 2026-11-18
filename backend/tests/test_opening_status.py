from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.core.db import connect_db
from app.services import toilet_service


def schedule(start="08:00", end="18:00", all_day=False, previous=(None, None)):
    return {
        "today_open": start,
        "today_close": end,
        "today_24h": all_day,
        "yesterday_open": previous[0],
        "yesterday_close": previous[1],
        "yesterday_24h": False,
    }


def local_time(hour, minute=0):
    return datetime(2026, 11, 16, hour, minute, tzinfo=ZoneInfo("Asia/Taipei"))


@pytest.mark.parametrize(
    ("hour", "minute", "expected"),
    [(7, 59, False), (8, 0, True), (17, 59, True), (18, 0, False)],
)
def test_opening_boundaries(hour, minute, expected):
    assert toilet_service._opening_status(schedule(), local_time(hour, minute)) == (
        expected,
        "08:00–18:00",
    )


@pytest.mark.parametrize(
    "start,end", [(None, None), ("00:00", "00:00"), ("08:00", "08:00"), ("bad", "18:00")]
)
def test_ambiguous_hours_are_unknown(start, end):
    assert toilet_service._opening_status(schedule(start, end), local_time(10)) == (
        None,
        "Hours unavailable",
    )


def test_explicit_24_hours_is_open():
    assert toilet_service._opening_status(schedule(all_day=True), local_time(23)) == (
        True,
        "Open 24 hours",
    )


def test_overnight_schedule_uses_previous_day_after_midnight():
    yesterday = ("22:00", "02:00")
    assert toilet_service._opening_status(schedule(previous=yesterday), local_time(1))[0] is True
    assert toilet_service._opening_status(schedule(previous=yesterday), local_time(2))[0] is False
    assert toilet_service._opening_status(schedule("22:00", "02:00"), local_time(23)) == (
        True,
        "22:00–02:00 (next day)",
    )
    # Today's late opening must not imply that yesterday was also open overnight.
    assert toilet_service._opening_status(schedule("22:00", "02:00"), local_time(1))[0] is False


def test_previous_day_24_hours_does_not_extend_into_today():
    row = schedule()
    row["yesterday_24h"] = True
    assert toilet_service._opening_status(row, local_time(1))[0] is False


def test_api_uses_current_hours_for_status_and_filters(client, monkeypatch):
    monkeypatch.setattr(toilet_service, "_local_now", lambda: local_time(1))
    with connect_db() as conn:
        conn.execute(
            "UPDATE opening_hours SET open_time = '08:00', close_time = '18:00', is_24h = 0 "
            "WHERE toilet_id = 'tp_001'"
        )
        # Sunday overnight hours must carry into Monday morning.
        conn.execute(
            "UPDATE opening_hours SET open_time = '22:00', close_time = '02:00' "
            "WHERE toilet_id = 'tp_001' AND day_of_week = 6"
        )
        conn.execute("UPDATE toilets SET open_now = 0 WHERE id = 'tp_001'")
    detail = client.get("/v1/toilets/tp_001").json()
    assert detail["openNow"] is True
    assert detail["openLabel"] == "08:00–18:00"
    assert "tp_001" in {
        item["id"] for item in client.get("/v1/toilets", params={"open_now": True}).json()["items"]
    }
    monkeypatch.setattr(toilet_service, "_local_now", lambda: local_time(18))
    assert client.get("/v1/toilets/tp_001").json()["openNow"] is False
    assert "tp_001" not in {
        item["id"]
        for item in client.get(
            "/v1/toilets/nearby", params={"lat": 25.0478, "lng": 121.517, "open_now": True}
        ).json()["items"]
    }
