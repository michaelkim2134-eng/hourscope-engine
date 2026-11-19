from fastapi.testclient import TestClient

from hourscope_engine.api import app
from hourscope_engine.__main__ import main

client = TestClient(app)


def test_chart_endpoint_western_and_vedic():
    body = {"birth_date": "1879-03-14", "birth_time": "11:30", "latitude": 48.4,
            "longitude": 10.0, "timezone": "Europe/Berlin"}
    w = client.post("/v1/chart", json=body).json()
    assert w["system"] == "western" and w["ascendant"]["sign"] == "Cancer"
    v = client.post("/v1/chart", json={**body, "system": "vedic"}).json()
    assert v["zodiac"].startswith("sidereal") and v["planets"][0]["nakshatra"]


def test_chart_endpoint_unknown_time():
    r = client.post("/v1/chart", json={"birth_date": "1990-03-14", "latitude": 37.57, "longitude": 126.98})
    assert r.status_code == 200
    assert r.json()["ascendant"] is None and r.json()["timezone"] == "Asia/Seoul"


def test_chart_endpoint_rejects_bad_latitude():
    r = client.post("/v1/chart", json={"birth_date": "1990-03-14", "latitude": 120, "longitude": 0})
    assert r.status_code == 422


def test_places_endpoint():
    assert client.get("/v1/places", params={"q": "Seoul"}).json()[0]["timezone"] == "Asia/Seoul"


def test_command_line_prints_both_systems(capsys):
    assert main(["--date", "1879-03-14", "--time", "11:30", "--place", "Ulm, Germany"]) == 0
    out = capsys.readouterr().out
    assert "WESTERN" in out and "VEDIC" in out and "Lagna" in out


def test_day_endpoint():
    body = {"birth_date": "1990-03-14", "birth_time": "15:20", "latitude": 37.566, "longitude": 126.978,
            "date": "2026-11-10", "current_latitude": 40.7128, "current_longitude": -74.006, "system": "vedic"}
    r = client.post("/v1/day", json=body)
    assert r.status_code == 200
    d = r.json()
    assert d["timezone"] == "America/New_York" and 1 <= d["rating"] <= 10 and d["rahu_kaal"]
    assert len(d["hours"]) == 24 and d["best_hours"]


def test_today_command_prints_best_hours(capsys):
    from hourscope_engine.today import main as today_main
    assert today_main(["--birth-date", "1990-03-14", "--birth-time", "15:20", "--birth-place", "Seoul",
                       "--place", "New York", "--date", "2026-11-10"]) == 0
    out = capsys.readouterr().out
    assert "Best hours" in out and "Today's energy" in out


def test_nearest_place_endpoint():
    d = client.get("/v1/places/nearest", params={"lat": 40.75, "lon": -73.99}).json()
    assert d["timezone"] == "America/New_York" and d["point_timezone"] == "America/New_York"


def test_engine_key_required_when_set(monkeypatch):
    monkeypatch.setenv("ENGINE_API_KEY", "secret")
    assert client.get("/health").status_code == 401
    assert client.get("/health", headers={"X-Engine-Key": "secret"}).status_code == 200
    # The uptime check is open but says nothing beyond "running".
    live = client.get("/livez")
    assert live.status_code == 200 and live.json() == {"ok": True}


def test_days_endpoint_for_calendar():
    import time
    body = {"birth_date": "1990-03-14", "birth_time": "15:20", "latitude": 37.566, "longitude": 126.978,
            "start_date": "2026-11-01", "days": 30, "current_latitude": 40.7128, "current_longitude": -74.006}
    t0 = time.time()
    r = client.post("/v1/days", json=body)
    took = time.time() - t0
    assert r.status_code == 200
    d = r.json()
    assert len(d) == 30 and d[0]["date"] == "2026-11-01" and d[-1]["date"] == "2026-11-30"
    assert all(1 <= x["rating"] <= 10 and x["best_hours"] for x in d)
    assert took < 15, f"month took {took:.1f}s"
    assert client.post("/v1/days", json={**body, "days": 400}).status_code == 422


def test_power_days_endpoint():
    acts = client.get("/v1/activities").json()
    assert any(a["id"] == "launch" for a in acts["activities"])
    body = {"birth_date": "1990-03-14", "birth_time": "15:20", "latitude": 37.566, "longitude": 126.978,
            "activity": "launch", "start_date": "2026-11-13", "days": 14,
            "current_latitude": 33.45, "current_longitude": -112.07, "top": 5}
    r = client.post("/v1/power-days", json=body)
    assert r.status_code == 200
    d = r.json()
    assert d["activity"] == "launch" and 1 <= len(d["windows"]) <= 5
    assert client.post("/v1/power-days", json={**body, "activity": "nope"}).status_code == 422


def test_retrogrades_endpoint():
    r = client.get("/v1/retrogrades", params={"start": "2026-10-01", "days": 60})
    assert r.status_code == 200
    planets = {x["planet"] for x in r.json()}
    assert {"Mercury", "Venus"} <= planets
    assert client.get("/v1/retrogrades", params={"start": "2026-10-01", "days": 5000}).status_code == 422


def test_sky_frames_and_events_endpoints():
    f = client.get("/v1/sky-frames", params={"start": "2026-11-13", "days": 30})
    assert f.status_code == 200 and len(f.json()) == 31
    body = {"birth_date": "1990-03-14", "birth_time": "15:20", "latitude": 37.566, "longitude": 126.978,
            "start_date": "2026-11-13", "days": 120}
    e = client.post("/v1/transit-events", json=body)
    assert e.status_code == 200 and any(x["kind"] == "station" for x in e.json())
    assert client.get("/v1/sky-frames", params={"start": "2026-11-13", "days": 900}).status_code == 422


def test_lunations_and_rewind_endpoints():
    l = client.get("/v1/lunations", params={"start": "2026-11-01", "days": 40})
    assert l.status_code == 200 and {x["type"] for x in l.json()} == {"new", "full"}
    body = {"birth_date": "1990-03-14", "birth_time": "15:20", "latitude": 37.566, "longitude": 126.978,
            "dates": ["2019-06-01", "2010-09-15"]}
    r = client.post("/v1/rewind", json=body)
    assert r.status_code == 200 and len(r.json()) == 2
    assert client.post("/v1/rewind", json={**body, "dates": []}).status_code == 422
