"""Convert a local birth time to UTC using the historical time zone rules.

CLAUDE.md ground rule 3: never assume today's offset. We use the IANA time
zone database (Python's zoneinfo + the tzdata package), which records every
clock change in each region's history, including daylight saving and wartime
time.

Before a region adopted standard time, clocks ran on *local mean time*, set
by the Sun at that town's own longitude. The database only knows the mean
time of one reference city per zone (Berlin for all of Germany, for example),
so for those dates we compute local mean time from the birthplace's own
longitude, the way astrologers do. See docs/decisions.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

# Zones where births are recorded in each town's own local mean time even
# though the database lists a single city's mean time. Empty for now: for
# India before 1906, Astro-Databank uses Madras time like the database does
# (Nehru, 1889), so we follow the database there. See docs/decisions.md.
_LOCAL_MEAN_TIME_BEFORE: dict[str, date] = {}

# Zones whose historical records are known to be simplified, so the user
# should double-check the time standard on the birth certificate.
_UNCERTAIN_BEFORE: dict[str, tuple[date, str]] = {
    "Asia/Kolkata": (date(1956, 1, 1), "Bombay and Calcutta kept their own local times until the 1950s"),
    "Asia/Calcutta": (date(1956, 1, 1), "Bombay and Calcutta kept their own local times until the 1950s"),
}


@dataclass(frozen=True)
class LocalTimeResult:
    utc: datetime                  # timezone-aware, in UTC
    utc_offset: timedelta          # local minus UTC
    timezone_name: str             # IANA zone, e.g. "Europe/Berlin"
    abbreviation: str              # e.g. "CET", "EDT", "LMT"
    time_basis: str                # "zone", "local_mean_time" or "manual_offset"
    warnings: list[str] = field(default_factory=list)


def _lmt_offset(longitude: float) -> timedelta:
    # The Sun moves 15 degrees of longitude per hour.
    return timedelta(seconds=round(longitude / 15.0 * 3600))


def local_to_utc(
    birth_date: date,
    birth_time: time,
    timezone_name: str,
    longitude: float,
    manual_utc_offset_hours: float | None = None,
) -> LocalTimeResult:
    """Convert a local clock time at the birthplace to UTC.

    manual_utc_offset_hours overrides the database (for when a birth
    certificate states the time standard explicitly).
    """
    local = datetime.combine(birth_date, birth_time)

    if manual_utc_offset_hours is not None:
        offset = timedelta(hours=manual_utc_offset_hours)
        return LocalTimeResult(
            utc=(local - offset).replace(tzinfo=timezone.utc),
            utc_offset=offset,
            timezone_name=timezone_name,
            abbreviation="manual",
            time_basis="manual_offset",
        )

    zone = ZoneInfo(timezone_name)
    warnings: list[str] = []

    early = local.replace(tzinfo=zone, fold=0)
    late = local.replace(tzinfo=zone, fold=1)
    chosen = early
    if early.utcoffset() != late.utcoffset():
        round_trip = early.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None)
        if round_trip != local:
            warnings.append(
                "This clock time did not exist at the birthplace (the clocks jumped forward "
                "that night). We used the time before the change; please double-check the birth time."
            )
        else:
            warnings.append(
                "This clock time happened twice at the birthplace (the clocks went back that "
                "night). We used the first one; ask the user which one if it matters."
            )

    abbreviation = chosen.tzname() or ""
    lmt_cutoff = _LOCAL_MEAN_TIME_BEFORE.get(timezone_name)
    use_lmt = abbreviation == "LMT" or (lmt_cutoff is not None and birth_date < lmt_cutoff)

    if use_lmt:
        offset = _lmt_offset(longitude)
        basis = "local_mean_time"
        abbreviation = "LMT"
        warnings.append("Born before standard time was used here, so local mean time for the birthplace was used.")
    else:
        offset = chosen.utcoffset() or timedelta(0)
        basis = "zone"

    uncertain = _UNCERTAIN_BEFORE.get(timezone_name)
    if uncertain and birth_date < uncertain[0] and not use_lmt:
        warnings.append(f"Time zone history here is uncertain before {uncertain[0].year} ({uncertain[1]}).")

    return LocalTimeResult(
        utc=(local - offset).replace(tzinfo=timezone.utc),
        utc_offset=offset,
        timezone_name=timezone_name,
        abbreviation=abbreviation,
        time_basis=basis,
        warnings=warnings,
    )
