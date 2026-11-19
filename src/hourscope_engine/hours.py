"""Planetary hours (Western) / horas (Vedic), and Rahu Kaal.

How planetary hours work:
- The planetary day starts at sunrise, not midnight.
- Sunrise to sunset is split into 12 equal "day hours"; sunset to the next
  sunrise into 12 equal "night hours". So hours are longer in summer days.
- The first hour belongs to the planet that rules the weekday (Sunday: Sun,
  Monday: Moon, Tuesday: Mars, Wednesday: Mercury, Thursday: Jupiter,
  Friday: Venus, Saturday: Saturn). Each next hour goes to the next planet
  in the Chaldean order: Saturn, Jupiter, Mars, Sun, Venus, Mercury, Moon.
- Sunrise is measured at the user's CURRENT location (not the birthplace).

The Vedic hora system uses the same sequence, so one calculation serves both.

Near the poles the Sun may not rise or set for weeks. Then we fall back to
06:00 and 18:00 local clock time and say so in the warnings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from .sky import datetime_from_jd, jd_from_datetime, next_sunrise, next_sunset

CHALDEAN_ORDER = ["Saturn", "Jupiter", "Mars", "Sun", "Venus", "Mercury", "Moon"]
# Python: Monday = 0 ... Sunday = 6
WEEKDAY_RULERS = ["Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Sun"]
# Which eighth of the daytime is Rahu Kaal (1 = first eighth), Monday..Sunday.
RAHU_KAAL_PART = [2, 7, 5, 6, 4, 3, 8]


@dataclass
class PlanetaryHour:
    number: int            # 1-24 (1-12 day, 13-24 night)
    ruler: str
    start: datetime        # local time at the current location
    end: datetime
    is_day: bool

    @property
    def midpoint(self) -> datetime:
        return self.start + (self.end - self.start) / 2


@dataclass
class PlanetaryDay:
    date: date                 # the local calendar date the planetary day starts on
    timezone: str
    latitude: float
    longitude: float
    day_ruler: str
    sunrise: datetime
    sunset: datetime
    next_sunrise: datetime
    hours: list[PlanetaryHour]
    rahu_kaal: tuple[datetime, datetime]
    warnings: list[str] = field(default_factory=list)

    def hour_at(self, moment: datetime) -> PlanetaryHour | None:
        for h in self.hours:
            if h.start <= moment < h.end:
                return h
        return None


def ruler_sequence(day_ruler: str, count: int = 24) -> list[str]:
    start = CHALDEAN_ORDER.index(day_ruler)
    return [CHALDEAN_ORDER[(start + i) % 7] for i in range(count)]


def planetary_day(local_date: date, latitude: float, longitude: float, timezone_name: str) -> PlanetaryDay:
    """The planetary day that begins at sunrise on local_date at this place."""
    zone = ZoneInfo(timezone_name)
    warnings: list[str] = []
    midnight = datetime.combine(local_date, time(0, 0), tzinfo=zone)
    jd0 = jd_from_datetime(midnight)

    rise = next_sunrise(jd0, latitude, longitude)
    sset = next_sunset(rise, latitude, longitude) if rise is not None else None
    rise2 = next_sunrise(sset, latitude, longitude) if sset is not None else None
    # The sunrise found must fall on this local date, and the day must not run
    # for more than a day and a half (which would mean a polar summer).
    polar = (
        rise is None or sset is None or rise2 is None
        or datetime_from_jd(rise).astimezone(zone).date() != local_date
        or rise2 - rise > 1.5
    )
    if polar:
        warnings.append(
            "The Sun doesn't rise and set normally here today (polar day or night), "
            "so 06:00 and 18:00 local time were used as sunrise and sunset."
        )
        sunrise_dt = datetime.combine(local_date, time(6, 0), tzinfo=zone)
        sunset_dt = datetime.combine(local_date, time(18, 0), tzinfo=zone)
        next_rise_dt = datetime.combine(local_date + timedelta(days=1), time(6, 0), tzinfo=zone)
    else:
        sunrise_dt = datetime_from_jd(rise).astimezone(zone)
        sunset_dt = datetime_from_jd(sset).astimezone(zone)
        next_rise_dt = datetime_from_jd(rise2).astimezone(zone)

    day_ruler = WEEKDAY_RULERS[local_date.weekday()]
    rulers = ruler_sequence(day_ruler)
    day_len = (sunset_dt - sunrise_dt) / 12
    night_len = (next_rise_dt - sunset_dt) / 12
    hours: list[PlanetaryHour] = []
    for i in range(12):
        start = sunrise_dt + day_len * i
        end = sunset_dt if i == 11 else sunrise_dt + day_len * (i + 1)
        hours.append(PlanetaryHour(i + 1, rulers[i], start.astimezone(zone), end.astimezone(zone), True))
    for i in range(12):
        start = sunset_dt + night_len * i
        end = next_rise_dt if i == 11 else sunset_dt + night_len * (i + 1)
        hours.append(PlanetaryHour(i + 13, rulers[i + 12], start.astimezone(zone), end.astimezone(zone), False))

    part = RAHU_KAAL_PART[local_date.weekday()]
    eighth = (sunset_dt - sunrise_dt) / 8
    rahu = ((sunrise_dt + eighth * (part - 1)).astimezone(zone), (sunrise_dt + eighth * part).astimezone(zone))

    return PlanetaryDay(
        date=local_date, timezone=timezone_name, latitude=latitude, longitude=longitude,
        day_ruler=day_ruler, sunrise=sunrise_dt, sunset=sunset_dt, next_sunrise=next_rise_dt,
        hours=hours, rahu_kaal=rahu, warnings=warnings,
    )


def planetary_hour_at(moment: datetime, latitude: float, longitude: float, timezone_name: str) -> PlanetaryHour:
    """The planetary hour running at a given moment (timezone-aware)."""
    zone = ZoneInfo(timezone_name)
    local = moment.astimezone(zone)
    for d in (local.date(), local.date() - timedelta(days=1)):
        pd = planetary_day(d, latitude, longitude, timezone_name)
        h = pd.hour_at(local)
        if h is not None:
            return h
    raise RuntimeError("no planetary hour found")  # pragma: no cover
