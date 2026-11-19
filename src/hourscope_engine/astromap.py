"""Places: astrocartography, relocated charts, best cities and the city compass.

See docs/research/relationships-and-places.md (B1, B2, B4, B5).
- Lines (in mundo): from the planet's apparent right ascension a and
  declination d at birth and Greenwich apparent sidereal time t:
  MC line lon = a - t; IC = MC + 180; rising / setting at latitude phi:
  H0 = arccos(-tan(phi) tan(d)), lon = a -/+ H0 - t.
- Relocated chart: same moment, new place (Ascendant, Midheaven, houses).
- Influence: full within 150 km, falling linearly to 0 at 800 km.
- Best places: a built-in list of world cities ranked by the supportive
  lines near them for a theme (love, career, rest, adventure, growth).
- City compass (local space): each planet's compass bearing at the birth
  moment, seen from a given place.
Guidance for reflection and travel planning, not a promise about any place.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

import swisseph as swe

from .chart import SIGNS, BirthChart, chart_at_utc
from .places import timezone_at
from .sky import PLANET_IDS, ephe_flag, jd_from_datetime

LINE_PLANETS = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]
EARTH_KM = 6371.0
FULL_KM, ZERO_KM = 150.0, 800.0
ANGLES = ("MC", "IC", "ASC", "DSC")

THEMES = {
    "love": {("Venus", "*"): 1.0, ("Moon", "*"): 0.6, ("Jupiter", "DSC"): 0.8, ("Sun", "DSC"): 0.5},
    "career": {("Sun", "MC"): 1.0, ("Jupiter", "MC"): 1.0, ("Saturn", "MC"): 0.7, ("Mars", "MC"): 0.6, ("Mercury", "MC"): 0.6},
    "rest": {("Moon", "IC"): 1.0, ("Venus", "IC"): 0.9, ("Jupiter", "IC"): 0.9, ("Neptune", "IC"): 0.5, ("Moon", "*"): 0.4},
    "adventure": {("Jupiter", "ASC"): 1.0, ("Mars", "ASC"): 0.7, ("Uranus", "*"): 0.7, ("Sun", "ASC"): 0.6, ("Jupiter", "*"): 0.5},
    "growth": {("Jupiter", "*"): 1.0, ("Sun", "*"): 0.6, ("Venus", "*"): 0.5},
}
EDGE = {("Saturn", "ASC"), ("Saturn", "DSC"), ("Saturn", "IC"), ("Pluto", "*"), ("Mars", "DSC"), ("Neptune", "ASC")}

CITIES = [  # name, country, lat, lon
    ("New York", "US", 40.71, -74.01), ("Los Angeles", "US", 34.05, -118.24), ("Chicago", "US", 41.88, -87.63),
    ("San Francisco", "US", 37.77, -122.42), ("Miami", "US", 25.76, -80.19), ("Austin", "US", 30.27, -97.74),
    ("Seattle", "US", 47.61, -122.33), ("Denver", "US", 39.74, -104.99), ("Boston", "US", 42.36, -71.06),
    ("Phoenix", "US", 33.45, -112.07), ("Honolulu", "US", 21.31, -157.86), ("Washington", "US", 38.91, -77.04),
    ("Toronto", "CA", 43.65, -79.38), ("Vancouver", "CA", 49.28, -123.12), ("Montreal", "CA", 45.50, -73.57),
    ("Mexico City", "MX", 19.43, -99.13), ("Cancún", "MX", 21.16, -86.85), ("Havana", "CU", 23.11, -82.37),
    ("Bogotá", "CO", 4.71, -74.07), ("Lima", "PE", -12.05, -77.04), ("Santiago", "CL", -33.45, -70.67),
    ("Buenos Aires", "AR", -34.60, -58.38), ("São Paulo", "BR", -23.55, -46.63), ("Rio de Janeiro", "BR", -22.91, -43.17),
    ("London", "GB", 51.51, -0.13), ("Edinburgh", "GB", 55.95, -3.19), ("Dublin", "IE", 53.35, -6.26),
    ("Paris", "FR", 48.86, 2.35), ("Nice", "FR", 43.70, 7.27), ("Lisbon", "PT", 38.72, -9.14),
    ("Madrid", "ES", 40.42, -3.70), ("Barcelona", "ES", 41.39, 2.17), ("Amsterdam", "NL", 52.37, 4.90),
    ("Brussels", "BE", 50.85, 4.35), ("Berlin", "DE", 52.52, 13.40), ("Munich", "DE", 48.14, 11.58),
    ("Zurich", "CH", 47.38, 8.54), ("Vienna", "AT", 48.21, 16.37), ("Prague", "CZ", 50.08, 14.44),
    ("Copenhagen", "DK", 55.68, 12.57), ("Stockholm", "SE", 59.33, 18.07), ("Oslo", "NO", 59.91, 10.75),
    ("Helsinki", "FI", 60.17, 24.94), ("Reykjavík", "IS", 64.15, -21.94), ("Warsaw", "PL", 52.23, 21.01),
    ("Budapest", "HU", 47.50, 19.04), ("Rome", "IT", 41.90, 12.50), ("Milan", "IT", 45.46, 9.19),
    ("Athens", "GR", 37.98, 23.73), ("Istanbul", "TR", 41.01, 28.98), ("Moscow", "RU", 55.76, 37.62),
    ("Cairo", "EG", 30.04, 31.24), ("Marrakesh", "MA", 31.63, -8.01), ("Lagos", "NG", 6.52, 3.38),
    ("Nairobi", "KE", -1.29, 36.82), ("Cape Town", "ZA", -33.92, 18.42), ("Johannesburg", "ZA", -26.20, 28.05),
    ("Dubai", "AE", 25.20, 55.27), ("Tel Aviv", "IL", 32.09, 34.78), ("Doha", "QA", 25.29, 51.53),
    ("Mumbai", "IN", 19.08, 72.88), ("Delhi", "IN", 28.61, 77.21), ("Bengaluru", "IN", 12.97, 77.59),
    ("Chennai", "IN", 13.08, 80.27), ("Kolkata", "IN", 22.57, 88.36), ("Goa", "IN", 15.49, 73.83),
    ("Kathmandu", "NP", 27.72, 85.32), ("Colombo", "LK", 6.93, 79.86), ("Bangkok", "TH", 13.76, 100.50),
    ("Chiang Mai", "TH", 18.79, 98.98), ("Bali", "ID", -8.65, 115.22), ("Singapore", "SG", 1.35, 103.82),
    ("Kuala Lumpur", "MY", 3.14, 101.69), ("Hanoi", "VN", 21.03, 105.85), ("Ho Chi Minh City", "VN", 10.82, 106.63),
    ("Manila", "PH", 14.60, 120.98), ("Hong Kong", "HK", 22.32, 114.17), ("Taipei", "TW", 25.03, 121.57),
    ("Shanghai", "CN", 31.23, 121.47), ("Beijing", "CN", 39.90, 116.41), ("Seoul", "KR", 37.57, 126.98),
    ("Tokyo", "JP", 35.68, 139.69), ("Kyoto", "JP", 35.01, 135.77), ("Sydney", "AU", -33.87, 151.21),
    ("Melbourne", "AU", -37.81, 144.96), ("Perth", "AU", -31.95, 115.86), ("Brisbane", "AU", -27.47, 153.03),
    ("Auckland", "NZ", -36.85, 174.76), ("Queenstown", "NZ", -45.03, 168.66),
]


def _norm180(x: float) -> float:
    return (x + 180) % 360 - 180


def _gc_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_KM * math.asin(min(1.0, math.sqrt(a)))


def _equatorial(jd: float) -> tuple[dict[str, tuple[float, float]], float]:
    flags = ephe_flag() | swe.FLG_EQUATORIAL
    eq = {}
    for name in LINE_PLANETS:
        xx, _ = swe.calc_ut(jd, PLANET_IDS[name], flags)
        eq[name] = (xx[0], xx[1])      # right ascension, declination (degrees)
    gast = swe.sidtime(jd) * 15.0
    return eq, gast


def acg_lines(jd: float, lat_step: float = 2.0) -> dict:
    eq, gast = _equatorial(jd)
    lines = {}
    for name, (ra, dec) in eq.items():
        mc = _norm180(ra - gast)
        asc, dsc = [], []
        phi = -80.0
        while phi <= 80.0:
            x = -math.tan(math.radians(phi)) * math.tan(math.radians(dec))
            if abs(x) <= 1:
                h0 = math.degrees(math.acos(x))
                asc.append([round(phi, 2), round(_norm180(ra - h0 - gast), 3)])
                dsc.append([round(phi, 2), round(_norm180(ra + h0 - gast), 3)])
            phi += lat_step
        lines[name] = {"MC": round(mc, 3), "IC": round(_norm180(mc + 180), 3), "ASC": asc, "DSC": dsc}
    return lines


def distance_to_line(lat: float, lon: float, line: dict, angle: str) -> float:
    if angle in ("MC", "IC"):
        # An MC or IC line is half a meridian (pole to pole), not the whole great circle:
        # from the far side the nearest point is a pole.
        dl = _norm180(lon - line[angle])
        if abs(dl) > 90:
            return EARTH_KM * math.radians(90 - abs(lat))
        return EARTH_KM * abs(math.asin(max(-1.0, min(1.0, math.cos(math.radians(lat)) * math.sin(math.radians(dl))))))
    pts = line[angle]
    return min((_gc_km(lat, lon, p[0], p[1]) for p in pts), default=float("inf"))


def influence(km: float) -> float:
    if km <= FULL_KM:
        return 1.0
    return max(0.0, 1 - (km - FULL_KM) / (ZERO_KM - FULL_KM))


def nearby_lines(lines: dict, lat: float, lon: float, limit_km: float = ZERO_KM) -> list[dict]:
    out = []
    for name, ln in lines.items():
        for angle in ANGLES:
            d = distance_to_line(lat, lon, ln, angle)
            if d <= limit_km:
                out.append({"planet": name, "angle": angle, "km": round(d), "strength": round(influence(d), 2),
                            "edge": (name, angle) in EDGE or (name, "*") in EDGE})
    return sorted(out, key=lambda x: x["km"])


def theme_score(near: list[dict], theme: str) -> float:
    weights = THEMES[theme]
    s = 0.0
    for n in near:
        w = weights.get((n["planet"], n["angle"]), weights.get((n["planet"], "*"), 0.0))
        s += w * n["strength"]
        if n["edge"]:
            s -= 0.3 * n["strength"]
    return round(s, 3)


def relocated(chart: BirthChart, lat: float, lon: float, tz: str | None = None) -> dict:
    # Rule 4: without a birth time the noon chart has no real angles or houses, here or anywhere.
    if not chart.time_known:
        return {"ascendant": None, "midheaven": None, "sun_house": None, "moon_house": None, "angular": []}
    rc = chart_at_utc(datetime.fromisoformat(chart.utc_time), lat, lon, chart.system)
    angular = []
    if rc.ascendant is not None:
        pts = {"ASC": rc.ascendant.longitude, "DSC": (rc.ascendant.longitude + 180) % 360}
        if rc.midheaven is not None:
            pts.update({"MC": rc.midheaven.longitude, "IC": (rc.midheaven.longitude + 180) % 360})
        for p in rc.planets:
            if p.name in LINE_PLANETS:
                for ang, l2 in pts.items():
                    d = abs(_norm180(p.longitude - l2))
                    if d <= 5:
                        angular.append({"planet": p.name, "angle": ang, "orb": round(d, 1)})
    sun, moon = rc.planet("Sun"), rc.planet("Moon")
    return {"ascendant": rc.ascendant.sign if rc.ascendant else None, "midheaven": rc.midheaven.sign if rc.midheaven else None,
            "sun_house": sun.house, "moon_house": moon.house, "angular": angular}


def compass(chart: BirthChart, lat: float, lon: float) -> list[dict]:
    """Local space: each planet's bearing (degrees from north, clockwise) and altitude at the birth moment from a place."""
    jd = jd_from_datetime(datetime.fromisoformat(chart.utc_time))
    out = []
    for name in LINE_PLANETS:
        xx, _ = swe.calc_ut(jd, PLANET_IDS[name], ephe_flag())
        az, alt, _ = swe.azalt(jd, swe.ECL2HOR, (lon, lat, 0.0), 1013.25, 10.0, (xx[0], xx[1], xx[2]))
        bearing = (az + 180) % 360     # Swiss Ephemeris azimuth counts from south
        out.append({"planet": name, "bearing": round(bearing, 1), "altitude": round(alt, 1),
                    "direction": ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][int(((bearing + 22.5) % 360) // 45)]})
    return out


@dataclass
class AstroMap:
    lines: dict
    best: dict
    current: dict
    birthplace: dict
    compass: list[dict]
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def city_report(chart: BirthChart, lines: dict, name: str, lat: float, lon: float, tz: str | None = None) -> dict:
    near = nearby_lines(lines, lat, lon)
    return {"name": name, "latitude": lat, "longitude": lon, "lines": near, "relocated": relocated(chart, lat, lon, tz),
            "themes": {t: theme_score(near, t) for t in THEMES}}


def astro_map(chart: BirthChart, current: tuple[str, float, float, str | None]) -> AstroMap:
    jd = jd_from_datetime(datetime.fromisoformat(chart.utc_time))
    lines = acg_lines(jd)
    warnings = [] if chart.time_known else [
        "Birth time unknown: the lines can be off by hundreds of kilometres (the Earth turns 15 degrees an hour), so treat this map loosely."]
    scored = []
    for name, cc, lat, lon in CITIES:
        near = nearby_lines(lines, lat, lon)
        scored.append({"name": name, "country": cc, "latitude": lat, "longitude": lon,
                       "themes": {t: theme_score(near, t) for t in THEMES},
                       "top": [f"{n['planet']} {n['angle']}" for n in near[:3]]})
    best = {t: sorted((c for c in scored if c["themes"][t] > 0.2), key=lambda c: -c["themes"][t])[:6] for t in THEMES}
    cname, clat, clon, ctz = current
    bp = (chart.latitude, chart.longitude)
    return AstroMap(lines, best, city_report(chart, lines, cname, clat, clon, ctz),
                    city_report(chart, lines, "Birthplace", bp[0], bp[1], chart.timezone), compass(chart, clat, clon), warnings)
