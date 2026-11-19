"""Annual and monthly profections ("Your Year").

Hellenistic whole-sign method (see docs/research/western-depth-and-timing.md, 3.1):
- each year of life moves one sign forward from the Ascendant sign: age 0 is
  the 1st house, age 1 the 2nd, ... and the cycle repeats every 12 years;
- the year turns at the exact solar return (the Sun back on its natal degree);
- the traditional ruler of the year's sign is the "lord of the year";
- monthly profections: month m begins when the Sun reaches natal Sun + 30*m
  degrees, and moves one more sign forward each month.
Without a birth time the Sun's sign stands in for the Ascendant (lower confidence).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime

from .chart import SIGNS, BirthChart
from .insights import TRADITIONAL_RULERS, dignity, vedic_dignity
from .sky import datetime_from_jd, jd_from_datetime
from .transits import _exact_times

YEAR = 365.2422


@dataclass
class ProfectionMonth:
    index: int          # 0-11 within the profection year
    sign: str
    house: int
    lord: str
    starts: str
    ends: str


@dataclass
class Profection:
    basis: str          # "ascendant" or "sun" (birth time unknown)
    age: int
    sign: str
    house: int
    lord: str
    lord_natal: dict    # sign, house (None without birth time), dignity
    natal_planets_in_sign: list[str]
    starts: str         # the solar return that began this year (UTC ISO)
    ends: str           # the next solar return
    month: ProfectionMonth
    table: list[dict] = field(default_factory=list)   # ages 0-100: sign, house, lord
    months: list[dict] = field(default_factory=list)  # all 12 months of this year (same shape as `month`)

    def to_dict(self) -> dict:
        return asdict(self)


def _sign_from(start: str, steps: int) -> str:
    return SIGNS[(SIGNS.index(start) + steps) % 12]


def _returns(natal_sun: float, jd0: float, jd1: float, sidereal: bool) -> list[float]:
    return _exact_times("Sun", natal_sun, 0.0, jd0, jd1, sidereal)


def profection(chart: BirthChart, at: datetime) -> Profection:
    sidereal = chart.system == "vedic"
    sun = chart.planet("Sun")
    basis = "ascendant" if chart.ascendant is not None else "sun"
    first_sign = chart.ascendant.sign if chart.ascendant is not None else sun.sign
    birth_jd = jd_from_datetime(datetime.fromisoformat(chart.utc_time))
    now = jd_from_datetime(at)

    # The solar returns around now: the last one at or before now, and the next.
    found = _returns(sun.longitude, now - 400, now + 400, sidereal)
    past = [t for t in found if t <= now]
    future = [t for t in found if t > now]
    last = past[-1] if past and past[-1] - birth_jd > 300 else birth_jd   # first year runs from birth
    nxt = future[0]
    age = max(0, round((last - birth_jd) / YEAR))

    sign = _sign_from(first_sign, age)
    lord = TRADITIONAL_RULERS[sign]
    lp = chart.planet(lord)
    lord_dignity = vedic_dignity(lord, lp.longitude) if sidereal else dignity(lord, lp.sign)
    in_sign = [p.name for p in chart.planets if p.sign == sign and p.name not in ("South Node", "Ketu")]

    # Monthly: which 30-degree step of the Sun since the return are we in?
    month_starts = [last]
    for m in range(1, 12):
        hits = _exact_times("Sun", (sun.longitude + 30 * m) % 360, 0.0, last, nxt, sidereal)
        month_starts.append(hits[0] if hits else last + m * (nxt - last) / 12)
    month_starts.append(nxt)
    m = max(i for i in range(12) if month_starts[i] <= now)
    m_sign = _sign_from(sign, m)

    iso = lambda jd: datetime_from_jd(jd).isoformat()  # noqa: E731
    return Profection(
        basis=basis, age=age, sign=sign, house=age % 12 + 1, lord=lord,
        lord_natal={"sign": lp.sign, "house": lp.house if basis == "ascendant" else None, "dignity": lord_dignity},
        natal_planets_in_sign=in_sign,
        starts=iso(last), ends=iso(nxt),
        month=ProfectionMonth(m, m_sign, (age + m) % 12 + 1, TRADITIONAL_RULERS[m_sign],
                              iso(month_starts[m]), iso(month_starts[m + 1])),
        table=[{"age": a, "sign": _sign_from(first_sign, a), "house": a % 12 + 1,
                "lord": TRADITIONAL_RULERS[_sign_from(first_sign, a)]} for a in range(101)],
        months=[{"index": i, "sign": _sign_from(sign, i), "house": (age + i) % 12 + 1,
                 "lord": TRADITIONAL_RULERS[_sign_from(sign, i)], "starts": iso(month_starts[i]), "ends": iso(month_starts[i + 1])}
                for i in range(12)],
    )
