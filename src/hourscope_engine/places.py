"""Turn a place name into coordinates and an IANA time zone.

This uses an offline list of about 34,000 cities with 15,000+ people
(GeoNames, via the geonamescache package), so no birth data leaves the
machine. Small villages are not in it: callers can always pass exact
latitude/longitude instead, and the time zone is then looked up from the
coordinates. The website's birthplace search (step 3) can use a richer
geocoder and hand the engine coordinates.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from functools import lru_cache

import geonamescache
from timezonefinder import TimezoneFinder


@dataclass(frozen=True)
class Place:
    name: str
    country_code: str
    admin1: str
    latitude: float
    longitude: float
    timezone: str
    population: int


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(text.lower().replace(".", " ").split())


@lru_cache(maxsize=1)
def _index() -> tuple[dict[str, list[Place]], dict[str, str]]:
    gc = geonamescache.GeonamesCache()
    countries = gc.get_countries()
    # country name / ISO code -> ISO code
    country_lookup: dict[str, str] = {}
    for code, info in countries.items():
        country_lookup[_norm(code)] = code
        country_lookup[_norm(info["name"])] = code
        if info.get("iso3"):
            country_lookup[_norm(info["iso3"])] = code
    country_lookup.update({"usa": "US", "united states of america": "US", "uk": "GB",
                           "england": "GB", "scotland": "GB", "wales": "GB",
                           "south korea": "KR", "korea": "KR"})

    by_name: dict[str, list[Place]] = {}
    for city in gc.get_cities().values():
        place = Place(
            name=city["name"],
            country_code=city["countrycode"],
            admin1=city.get("admin1code", ""),
            latitude=float(city["latitude"]),
            longitude=float(city["longitude"]),
            timezone=city["timezone"],
            population=int(city.get("population") or 0),
        )
        names = {_norm(city["name"])}
        for alt in (city.get("alternatenames") or []):
            if alt:
                names.add(_norm(alt))
        for n in names:
            by_name.setdefault(n, []).append(place)
    return by_name, country_lookup


def find_place(query: str, limit: int = 5) -> list[Place]:
    """Find cities matching e.g. "Seoul", "Ulm, Germany" or "Bay City, MI, US".

    Results are sorted with the most populous match first. Returns an empty
    list when nothing matches; the caller should then ask for coordinates.
    """
    by_name, country_lookup = _index()
    parts = [p.strip() for p in query.split(",") if p.strip()]
    if not parts:
        return []
    city = _norm(parts[0])
    qualifiers = [_norm(p) for p in parts[1:]]

    matches = list(by_name.get(city, []))
    for q in qualifiers:
        code = country_lookup.get(q)
        narrowed = [
            m for m in matches
            if (code and m.country_code == code) or _norm(m.admin1) == q
        ]
        if narrowed:
            matches = narrowed
    # de-duplicate (a city can match through several alternate names)
    seen: set[tuple[str, float, float]] = set()
    unique = []
    for m in sorted(matches, key=lambda p: -p.population):
        key = (m.name, m.latitude, m.longitude)
        if key not in seen:
            seen.add(key)
            unique.append(m)
    return unique[:limit]


@lru_cache(maxsize=1)
def _tf() -> TimezoneFinder:
    return TimezoneFinder()


def timezone_at(latitude: float, longitude: float) -> str:
    """IANA time zone name for a point on Earth (e.g. 'Asia/Seoul')."""
    tz = _tf().timezone_at(lat=latitude, lng=longitude)
    if tz is None:
        # Open ocean: fall back to the nearest Etc/GMT zone.
        hours = round(longitude / 15)
        tz = "Etc/GMT" + ("+" if hours <= 0 else "-") + str(abs(hours)) if hours else "Etc/GMT"
    return tz


def nearest_place(latitude: float, longitude: float) -> Place:
    """Closest city in the offline list (for "use my current location")."""
    import math

    by_name, _ = _index()
    lat1 = math.radians(latitude)
    best: Place | None = None
    best_d = float("inf")
    seen: set[int] = set()
    for places in by_name.values():
        for p in places:
            if id(p) in seen:
                continue
            seen.add(id(p))
            lat2 = math.radians(p.latitude)
            dlat = lat2 - lat1
            dlon = math.radians(p.longitude - longitude)
            a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
            if a < best_d:
                best_d, best = a, p
    assert best is not None
    return best
