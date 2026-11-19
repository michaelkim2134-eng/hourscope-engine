"""Private HTTP API for the engine (the website calls this).

Run locally:  uvicorn hourscope_engine.api:app --reload
"""

from __future__ import annotations

import datetime as dt
from datetime import date, time
from typing import Literal

import hmac

from starlette.responses import JSONResponse
from starlette.routing import Route
import os

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from .chart import compute_chart
from datetime import timedelta

from .daily import daily_report
from .retrogrades import retrogrades_between
from .lunar import lunations
from .insights import sect_and_fortune
from .life_areas import life_areas
from .planet_cards import planet_cards
from .astromap import astro_map
from .compatibility import compatibility
from .seasons import seasons
from .vedic_seasons import vedic_seasons
from .profections import profection
from .soul import soul_path
from .transits import sky_frames, sky_on, transit_events
from .electional import ACTIVITIES, MAX_DAYS, RULES_VERSION, find_power_windows
from .insights import chart_insights
from .numerology import full_profile
from .places import find_place, nearest_place, timezone_at
from .social import sky_day



PRODUCTION = os.environ.get("HOURSCOPE_ENV", "").lower() == "production"
if PRODUCTION and not os.environ.get("ENGINE_API_KEY"):
    raise RuntimeError("ENGINE_API_KEY must be set when HOURSCOPE_ENV=production (the engine is private).")


def require_key(x_engine_key: str | None = Header(default=None)) -> None:
    """The engine is private: when ENGINE_API_KEY is set, callers must send it (constant-time check)."""
    expected = os.environ.get("ENGINE_API_KEY")
    if expected and not hmac.compare_digest((x_engine_key or "").encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="missing or wrong engine key")


# In production the interactive docs are switched off (they bypass the key check).
app = FastAPI(
    title="Hourscope Ephemeris Engine", version="0.1.0", dependencies=[Depends(require_key)],
    docs_url=None if PRODUCTION else "/docs", redoc_url=None if PRODUCTION else "/redoc",
    openapi_url=None if PRODUCTION else "/openapi.json",
)


class ChartRequest(BaseModel):
    birth_date: date
    birth_time: time | None = Field(None, description="Leave empty if unknown: a noon chart is used.")
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    timezone: str | None = Field(None, description="IANA zone; looked up from coordinates if empty.")
    utc_offset_hours: float | None = Field(None, description="Force an offset (overrides the time zone database).")
    system: Literal["western", "vedic"] = "western"


CHART_VERSION = "2026-11-15.1"  # bump when chart calculations change


async def _livez(_request) -> JSONResponse:
    return JSONResponse({"ok": True})


# For the host's uptime check, which can't send the key: says only "running", nothing else.
# A plain Starlette route, so the app-wide key check doesn't apply to it.
app.router.routes.append(Route("/livez", _livez, methods=["GET"]))


@app.get("/health")
def health() -> dict:
    from .daily import SCORING_VERSION

    return {"ok": True, "scoring_version": SCORING_VERSION, "chart_version": CHART_VERSION, "rules_version": RULES_VERSION}


@app.post("/v1/chart")
def chart(req: ChartRequest) -> dict:
    try:
        c = compute_chart(
            req.birth_date, req.birth_time, req.latitude, req.longitude,
            req.timezone, req.system, req.utc_offset_hours,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return c.to_dict()


@app.get("/v1/places")
def places(q: str, limit: int = 5) -> list[dict]:
    return [p.__dict__ for p in find_place(q, limit=min(limit, 20))]


@app.get("/v1/places/nearest")
def places_nearest(lat: float, lon: float) -> dict:
    """Nearest city plus the time zone at the exact point."""
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise HTTPException(status_code=422, detail="latitude/longitude out of range")
    p = nearest_place(lat, lon)
    return {**p.__dict__, "point_timezone": timezone_at(lat, lon)}


class DayRequest(ChartRequest):
    date: dt.date = Field(..., description="The local date at the user's current location.")
    current_latitude: float = Field(..., ge=-90, le=90)
    current_longitude: float = Field(..., ge=-180, le=180)
    current_timezone: str | None = None


@app.post("/v1/day")
def day(req: DayRequest) -> dict:
    """Today's rating, theme and best hours at the user's current location."""
    try:
        c = compute_chart(
            req.birth_date, req.birth_time, req.latitude, req.longitude,
            req.timezone, req.system, req.utc_offset_hours,
        )
        r = daily_report(c, req.birth_date, req.date, req.current_latitude,
                         req.current_longitude, req.current_timezone)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return r.to_dict()


class DaysRequest(ChartRequest):
    start_date: dt.date
    days: int = Field(7, ge=1, le=62)
    current_latitude: float = Field(..., ge=-90, le=90)
    current_longitude: float = Field(..., ge=-180, le=180)
    current_timezone: str | None = None


@app.post("/v1/days")
def days(req: DaysRequest) -> list[dict]:
    """A compact summary for each day in a range (for the calendar)."""
    try:
        c = compute_chart(
            req.birth_date, req.birth_time, req.latitude, req.longitude,
            req.timezone, req.system, req.utc_offset_hours,
        )
        out = []
        for i in range(req.days):
            d = req.start_date + timedelta(days=i)
            r = daily_report(c, req.birth_date, d, req.current_latitude,
                             req.current_longitude, req.current_timezone)
            out.append({
                "date": r.date,
                "rating": r.rating,
                "day_ruler": r.day_ruler,
                "personal_day": r.numerology["personal_day"],
                "moon_sign": r.moon["sign"],
                "moon_phase": r.moon["phase"],
                "tithi": r.moon["tithi"] if r.system == "vedic" else None,
                "key_transit": r.theme["key_transit"],
                "best_hours": [
                    {"start": h.start, "end": h.end, "ruler": h.ruler, "score": h.score}
                    for h in r.best_hours
                ],
                "scoring_version": r.scoring_version,
            })
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return out


@app.post("/v1/insights")
def insights(req: ChartRequest) -> dict:
    """The chart plus deeper facts (balance, patterns, rulers; Vedic dashas, navamsa, yogas)."""
    try:
        c = compute_chart(
            req.birth_date, req.birth_time, req.latitude, req.longitude,
            req.timezone, req.system, req.utc_offset_hours,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return {"chart": c.to_dict(), "insights": chart_insights(c).to_dict()}


class NumerologyRequest(BaseModel):
    birth_date: dt.date
    full_name: str | None = Field(None, max_length=200)
    on: dt.date | None = None


@app.post("/v1/numerology")
def numerology(req: NumerologyRequest) -> dict:
    return full_profile(req.birth_date, req.full_name, req.on or dt.date.today())


@app.get("/v1/activities")
def activities() -> dict:
    """Activities the Power Day Finder knows about."""
    return {"rules_version": RULES_VERSION, "max_days": MAX_DAYS,
            "activities": [{"id": a.id, "label": a.label, "planets": list(a.primary + a.supporting)} for a in ACTIVITIES.values()]}


class PowerRequest(ChartRequest):
    activity: str
    start_date: dt.date
    days: int = Field(30, ge=1, le=MAX_DAYS)
    current_latitude: float = Field(..., ge=-90, le=90)
    current_longitude: float = Field(..., ge=-180, le=180)
    current_timezone: str | None = None
    top: int = Field(10, ge=1, le=30)


@app.post("/v1/power-days")
def power_days(req: PowerRequest) -> dict:
    """The best windows for an activity over a date range, ranked, with reasons."""
    try:
        c = compute_chart(
            req.birth_date, req.birth_time, req.latitude, req.longitude,
            req.timezone, req.system, req.utc_offset_hours,
        )
        windows = find_power_windows(
            c, req.birth_date, req.activity, req.start_date, req.days,
            req.current_latitude, req.current_longitude, req.current_timezone, req.top,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return {"rules_version": RULES_VERSION, "activity": req.activity, "windows": [w.to_dict() for w in windows]}


@app.get("/v1/retrogrades")
def retrogrades(start: dt.date, days: int = 120, system: Literal["western", "vedic"] = "western") -> list[dict]:
    """Retrograde periods (with shadow dates) that touch the range."""
    if not 1 <= days <= 730:
        raise HTTPException(status_code=422, detail="days must be between 1 and 730")
    from .sky import jd_from_datetime

    jd0 = jd_from_datetime(dt.datetime.combine(start, dt.time(0, 0), tzinfo=dt.timezone.utc))
    return [r.to_dict() for r in retrogrades_between(jd0, jd0 + days, sidereal=system == "vedic")]


def _jd(d: dt.date) -> float:
    from .sky import jd_from_datetime

    return jd_from_datetime(dt.datetime.combine(d, dt.time(0, 0), tzinfo=dt.timezone.utc))


@app.get("/v1/sky-frames")
def sky(start: dt.date, days: int = 366, step_hours: float = 24, system: Literal["western", "vedic"] = "western") -> list[dict]:
    """Planet positions at regular steps (for the Living Wheel and Time Scrubber)."""
    if not 1 <= days <= 400 or not 1 <= step_hours <= 48:
        raise HTTPException(status_code=422, detail="days must be 1-400 and step_hours 1-48")
    return sky_frames(_jd(start), days, step_hours, sidereal=system == "vedic")


class EventsRequest(ChartRequest):
    start_date: dt.date
    days: int = Field(366, ge=1, le=400)


@app.post("/v1/transit-events")
def events(req: EventsRequest) -> list[dict]:
    """Big moments for this person: transits to key points, returns, eclipses, stations, ingresses, dasha changes."""
    try:
        c = compute_chart(
            req.birth_date, req.birth_time, req.latitude, req.longitude,
            req.timezone, req.system, req.utc_offset_hours,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return [e.to_dict() for e in transit_events(c, _jd(req.start_date), req.days)]


class ProfectionRequest(ChartRequest):
    on: dt.date | None = Field(None, description="Date to look at (defaults to today, UTC).")


@app.post("/v1/profections")
def profections_endpoint(req: ProfectionRequest) -> dict:
    """Your Year: the activated house, lord of the year, this month's sub-theme, and ages 0-100."""
    try:
        c = compute_chart(
            req.birth_date, req.birth_time, req.latitude, req.longitude,
            req.timezone, req.system, req.utc_offset_hours,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    when = dt.datetime.combine(req.on, dt.time(12, 0), tzinfo=dt.timezone.utc) if req.on else dt.datetime.now(dt.timezone.utc)
    return profection(c, when).to_dict()


@app.post("/v1/soul")
def soul_endpoint(req: ProfectionRequest) -> dict:
    """Soul Path: nodal axis and cycle, Saturn as teacher, polarity, mission, growth planet, Vedic karakas."""
    try:
        c = compute_chart(
            req.birth_date, req.birth_time, req.latitude, req.longitude,
            req.timezone, req.system, req.utc_offset_hours,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    when = dt.datetime.combine(req.on, dt.time(12, 0), tzinfo=dt.timezone.utc) if req.on else dt.datetime.now(dt.timezone.utc)
    return soul_path(c, when).to_dict()


@app.post("/v1/life-areas")
def life_areas_endpoint(req: ChartRequest) -> dict:
    """The 12 life areas (house lords, occupants, Vedic aspects), exchanges, and the rising sign's cast."""
    try:
        c = compute_chart(
            req.birth_date, req.birth_time, req.latitude, req.longitude,
            req.timezone, req.system, req.utc_offset_hours,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return life_areas(c).to_dict()


@app.post("/v1/planets")
def planets_endpoint(req: ChartRequest) -> dict:
    """Planet report cards: dignity, accidental strength, sect, dispositors, receptions, keynotes, theme."""
    try:
        c = compute_chart(
            req.birth_date, req.birth_time, req.latitude, req.longitude,
            req.timezone, req.system, req.utc_offset_hours,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    sect, _ = sect_and_fortune(c)
    return planet_cards(c, sect).to_dict()


class SeasonsRequest(ChartRequest):
    on: dt.date | None = None
    current_latitude: float = Field(..., ge=-90, le=90)
    current_longitude: float = Field(..., ge=-180, le=180)
    current_timezone: str | None = None


@app.post("/v1/seasons")
def seasons_endpoint(req: SeasonsRequest) -> dict:
    """Inner Seasons (progressions, solar arc) and the Birthday Chart (solar and lunar returns at the current city)."""
    try:
        c = compute_chart(
            req.birth_date, req.birth_time, req.latitude, req.longitude,
            req.timezone, req.system, req.utc_offset_hours,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    when = dt.datetime.combine(req.on, dt.time(12, 0), tzinfo=dt.timezone.utc) if req.on else dt.datetime.now(dt.timezone.utc)
    tz = req.current_timezone or timezone_at(req.current_latitude, req.current_longitude)
    return seasons(c, when, req.current_latitude, req.current_longitude, tz).to_dict()


@app.post("/v1/vedic-seasons")
def vedic_seasons_endpoint(req: ProfectionRequest) -> dict:
    """Vedic seasons: Ashtakavarga, transits from the Moon with vedha, Sade Sati and Dhaiya, pratyantar and Yogini dashas."""
    try:
        c = compute_chart(
            req.birth_date, req.birth_time, req.latitude, req.longitude,
            req.timezone, "vedic", req.utc_offset_hours,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    when = dt.datetime.combine(req.on, dt.time(12, 0), tzinfo=dt.timezone.utc) if req.on else dt.datetime.now(dt.timezone.utc)
    return vedic_seasons(c, when).to_dict()


class Person(BaseModel):
    birth_date: dt.date
    birth_time: dt.time | None = None
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    timezone: str | None = None


class CompatibilityRequest(BaseModel):
    a: Person
    b: Person


@app.post("/v1/compatibility")
def compatibility_endpoint(req: CompatibilityRequest) -> dict:
    """Compatibility Studio: Ashtakoota, Manglik, Western synastry, karmic contacts and composite signs."""
    try:
        return compatibility(req.a.model_dump(), req.b.model_dump()).to_dict()
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


class AstroMapRequest(ChartRequest):
    place_name: str = Field("Current city", max_length=120)
    place_latitude: float = Field(..., ge=-90, le=90)
    place_longitude: float = Field(..., ge=-180, le=180)
    place_timezone: str | None = None


def _natal(req: ChartRequest):
    try:
        return compute_chart(req.birth_date, req.birth_time, req.latitude, req.longitude, req.timezone, req.system, req.utc_offset_hours)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@app.post("/v1/astromap")
def astromap_endpoint(req: AstroMapRequest) -> dict:
    """Places: planet lines, best cities per theme, the current city and birthplace, and the city compass."""
    c = _natal(req)
    return astro_map(c, (req.place_name, req.place_latitude, req.place_longitude, req.place_timezone)).to_dict()


@app.post("/v1/astromap/city")
def astromap_city_endpoint(req: AstroMapRequest) -> dict:
    """One place: nearby planet lines, the relocated chart and theme scores."""
    from .astromap import acg_lines, city_report
    from .sky import jd_from_datetime
    c = _natal(req)
    lines = acg_lines(jd_from_datetime(dt.datetime.fromisoformat(c.utc_time)))
    return city_report(c, lines, req.place_name, req.place_latitude, req.place_longitude, req.place_timezone)


@app.get("/v1/sky-day")
def sky_day_endpoint(date: dt.date, lat: float, lon: float, tz: str | None = None, place: str | None = None) -> dict:
    """The public sky for one local day (facts for social posts, not about any one person)."""
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise HTTPException(status_code=422, detail="latitude/longitude out of range")
    try:
        return sky_day(date, lat, lon, tz or timezone_at(lat, lon), place)
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@app.get("/v1/lunations")
def lunations_endpoint(start: dt.date, days: int = 60, system: Literal["western", "vedic"] = "western") -> list[dict]:
    """Exact new and full Moons in the range."""
    if not 1 <= days <= 400:
        raise HTTPException(status_code=422, detail="days must be between 1 and 400")
    jd0 = _jd(start)
    return lunations(jd0, jd0 + days, sidereal=system == "vedic")


class RewindRequest(ChartRequest):
    dates: list[dt.date] = Field(..., min_length=1, max_length=60)


@app.post("/v1/rewind")
def rewind(req: RewindRequest) -> list[dict]:
    """What the sky was doing on each date, compared with this birth chart."""
    try:
        c = compute_chart(
            req.birth_date, req.birth_time, req.latitude, req.longitude,
            req.timezone, req.system, req.utc_offset_hours,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return [sky_on(c, req.birth_date, d) for d in req.dates]
