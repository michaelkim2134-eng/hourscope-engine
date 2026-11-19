"""The Vedic day (panchanga) and the person's own stars for it.

The five limbs are taken at sunrise at the user's current location (the Vedic
day runs sunrise to sunrise), with the time each one changes during the day:
- vara (weekday lord), tithi (lunar day), nakshatra (Moon's star),
  nitya yoga (Sun + Moon), karana (half tithi);
- day windows: Rahu Kaal, Yamaganda, Gulika (eighths of daylight) and
  Abhijit muhurta (the 8th of 15 day muhurtas, around local noon);
- personal: tara bala (today's Moon star counted from the birth star),
  special stars, and chandra bala (Moon sign counted from the natal Moon sign).

Sources: P.V.R. Narasimha Rao, Vedic Astrology: An Integrated Approach (formulas,
taras, chandra bala); Saptarishis Astrology vol. 6 (Gulika and Yamaganda parts).
See docs/research/vedic-timing.md. All longitudes are sidereal (Lahiri).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime

from .chart import NAKSHATRA_SPAN, NAKSHATRAS, SIGNS, _NAKSHATRA_LORDS
from .hours import PlanetaryDay
from .lunar import TITHIS
from .sky import bisect_root, datetime_from_jd, jd_from_datetime, longitude_of

NITYA_YOGAS = [
    "Vishkambha", "Priti", "Ayushman", "Saubhagya", "Shobhana", "Atiganda", "Sukarma", "Dhriti", "Shula",
    "Ganda", "Vriddhi", "Dhruva", "Vyaghata", "Harshana", "Vajra", "Siddhi", "Vyatipata", "Variyan",
    "Parigha", "Shiva", "Siddha", "Sadhya", "Shubha", "Shukla", "Brahma", "Indra", "Vaidhriti",
]
# Traditionally avoided for new starts (general practice).
AVOIDED_YOGAS = {"Vishkambha", "Atiganda", "Shula", "Ganda", "Vyaghata", "Vajra", "Vyatipata", "Parigha", "Vaidhriti"}
MOVABLE_KARANAS = ["Bava", "Balava", "Kaulava", "Taitila", "Garaja", "Vanija", "Vishti"]

# Eighths of daylight (Monday-first, like date.weekday()). Rahu Kaal lives in hours.py.
GULIKA_PART = [6, 5, 4, 3, 2, 1, 7]      # Saturn's part: Sun 7, Mon 6 ... Sat 1
YAMAGANDA_PART = [4, 3, 2, 1, 7, 6, 5]   # Jupiter's part: Sun 5, Mon 4 ... Sat 6
WEEKDAY_NAMES = ["Somavara", "Mangalavara", "Budhavara", "Guruvara", "Shukravara", "Shanivara", "Ravivara"]

TARAS = [
    ("Janma", "mixed"), ("Sampat", "good"), ("Vipat", "challenging"), ("Kshema", "good"),
    ("Pratyak", "challenging"), ("Sadhana", "good"), ("Naidhana", "rest"), ("Mitra", "good"),
    ("Parama Mitra", "good"),
]
# Personal stars counted from the birth star (1 = birth star itself).
SPECIAL_STARS = {10: "Karma", 13: "Abhisheka", 16: "Sanghatika", 18: "Samudayika", 25: "Manasa",
                 7: "Caution", 22: "Caution"}
CHANDRA_GOOD = {1, 3, 6, 7, 10, 11}


# ---------------------------------------------------------------- limbs as functions of time
def _sid(body: str, jd: float) -> float:
    return longitude_of(body, jd, True)[0]


def _elong(jd: float) -> float:
    return (longitude_of("Moon", jd)[0] - longitude_of("Sun", jd)[0]) % 360


def tithi_index(jd: float) -> int:          # 0..29
    return int(_elong(jd) // 12) % 30


def nakshatra_index(jd: float) -> int:      # 0..26
    return int(_sid("Moon", jd) / NAKSHATRA_SPAN + 1e-9) % 27


def yoga_index(jd: float) -> int:           # 0..26
    return int(((_sid("Sun", jd) + _sid("Moon", jd)) % 360) / NAKSHATRA_SPAN + 1e-9) % 27


def karana_index(jd: float) -> int:         # 0..59
    return int(_elong(jd) // 6) % 60


def karana_name(k: int) -> str:
    if k == 0:
        return "Kimstughna"
    if k >= 57:
        return ["Shakuni", "Chatushpada", "Naga"][k - 57]
    return MOVABLE_KARANAS[(k - 1) % 7]


def _next_change(index_of, jd_start: float, jd_end: float, step: float = 1 / 24) -> float | None:
    """First moment after jd_start (up to jd_end) when index_of changes."""
    start = index_of(jd_start)
    t = jd_start
    while t < jd_end:
        t2 = min(t + step, jd_end)
        if index_of(t2) != start:
            return bisect_root(lambda x: 0.5 if index_of(x) == start else -0.5, t, t2, 1e-5)
        t = t2
    return None


# ---------------------------------------------------------------- result
@dataclass
class Limb:
    name: str
    number: int | None = None
    ends_at: str | None = None      # local ISO time it changes, if before the next sunrise
    note: str | None = None         # e.g. "less ideal for new starts"
    next: str | None = None         # the name that follows when it changes


@dataclass
class Panchanga:
    vara: Limb
    tithi: Limb
    nakshatra: Limb
    yoga: Limb
    karana: Limb
    windows: dict[str, tuple[str, str] | None]   # rahu_kaal, yamaganda, gulika, abhijit
    personal: dict | None

    def to_dict(self) -> dict:
        return asdict(self)


def _segment(pd: PlanetaryDay, part: int) -> tuple[datetime, datetime]:
    eighth = (pd.sunset - pd.sunrise) / 8
    return pd.sunrise + eighth * (part - 1), pd.sunrise + eighth * part


def day_windows(pd: PlanetaryDay) -> dict[str, tuple[datetime, datetime] | None]:
    wd = pd.date.weekday()
    muhurta = (pd.sunset - pd.sunrise) / 15
    abhijit = (pd.sunrise + muhurta * 7, pd.sunrise + muhurta * 8)
    return {
        "rahu_kaal": pd.rahu_kaal,
        "yamaganda": _segment(pd, YAMAGANDA_PART[wd]),
        "gulika": _segment(pd, GULIKA_PART[wd]),
        "abhijit": None if wd == 2 else abhijit,   # traditionally not used on Wednesdays
    }


def tara_of(birth_nakshatra: int, moon_nakshatra: int) -> tuple[int, str, str]:
    """(tara 1-9, name, quality) for today's Moon star counted from the birth star (both 0-26)."""
    n = ((moon_nakshatra - birth_nakshatra) % 27) % 9 + 1
    name, quality = TARAS[n - 1]
    return n, name, quality


def chandra_bala(natal_moon_sign: str, moon_sign: str) -> tuple[int, str]:
    house = (SIGNS.index(moon_sign) - SIGNS.index(natal_moon_sign)) % 12 + 1
    quality = "rest" if house == 8 else "good" if house in CHANDRA_GOOD else "weak"
    return house, quality


def panchanga(pd: PlanetaryDay, natal_moon_lon: float | None = None, birth_time_known: bool = True) -> Panchanga:
    """Panchanga at sunrise for this planetary day; personal stars if the natal (sidereal) Moon is given."""
    zone = pd.sunrise.tzinfo
    rise = jd_from_datetime(pd.sunrise)
    next_rise = jd_from_datetime(pd.next_sunrise)

    def ends(index_of) -> tuple[str | None, int | None]:
        """When the limb changes (local ISO) and its index just after the change."""
        t = _next_change(index_of, rise, next_rise)
        if t is None:
            return None, None
        return datetime_from_jd(t).astimezone(zone).isoformat(), index_of(t + 1e-4)

    def tithi_label(i: int) -> str:
        pk = "Shukla" if i < 15 else "Krishna"
        return "Purnima" if i == 14 else "Amavasya" if i == 29 else f"{pk} {TITHIS[i % 15]}"

    t_end, t_next = ends(tithi_index)
    n_end, n_next = ends(nakshatra_index)
    y_end, y_next = ends(yoga_index)
    k_end, k_next = ends(karana_index)

    t_idx = tithi_index(rise)
    paksha = "Shukla" if t_idx < 15 else "Krishna"
    tithi_name = tithi_label(t_idx)
    n_idx = nakshatra_index(rise)
    moon_lon = _sid("Moon", rise)
    pada = int((moon_lon % NAKSHATRA_SPAN) / (NAKSHATRA_SPAN / 4)) + 1
    y_idx = yoga_index(rise)
    k_idx = karana_index(rise)
    k_name = karana_name(k_idx)
    rikta = (t_idx % 15) + 1 in (4, 9, 14) or t_idx == 29

    windows = {k: (v[0].isoformat(), v[1].isoformat()) if v else None for k, v in day_windows(pd).items()}

    personal = None
    if natal_moon_lon is not None:
        birth_n = int(natal_moon_lon / NAKSHATRA_SPAN + 1e-9) % 27
        tara, tara_name, quality = tara_of(birth_n, n_idx)
        count = (n_idx - birth_n) % 27 + 1
        natal_sign = SIGNS[int(natal_moon_lon // 30)]
        moon_sign = SIGNS[int(moon_lon // 30)]
        house, cb = chandra_bala(natal_sign, moon_sign)
        # Unknown birth time: the noon Moon may be in the neighbouring star (it moves ~6.5 deg in 12 hours).
        offset = natal_moon_lon % NAKSHATRA_SPAN
        uncertain = not birth_time_known and min(offset, NAKSHATRA_SPAN - offset) < 6.6
        personal = {
            "birth_nakshatra": NAKSHATRAS[birth_n],
            "tara": {"number": tara, "name": tara_name, "quality": quality},
            "star_count": count,
            "special_star": SPECIAL_STARS.get(count),
            "chandra_bala": {"house": house, "quality": cb, "natal_moon_sign": natal_sign},
            "uncertain": uncertain,
        }

    return Panchanga(
        vara=Limb(pd.day_ruler, note=WEEKDAY_NAMES[pd.date.weekday()]),
        tithi=Limb(tithi_name, t_idx + 1, t_end, "less ideal for new starts" if rikta else None,
                   tithi_label(t_next) if t_next is not None else None),
        nakshatra=Limb(NAKSHATRAS[n_idx], pada, n_end, f"ruled by {_NAKSHATRA_LORDS[n_idx % 9]}",
                       NAKSHATRAS[n_next] if n_next is not None else None),
        yoga=Limb(NITYA_YOGAS[y_idx], y_idx + 1, y_end,
                  "less ideal for new starts" if NITYA_YOGAS[y_idx] in AVOIDED_YOGAS else None,
                  NITYA_YOGAS[y_next] if y_next is not None else None),
        karana=Limb(k_name, k_idx + 1, k_end, "a pause: less ideal for new starts" if k_name == "Vishti" else None,
                    karana_name(k_next) if k_next is not None else None),
        windows=windows,
        personal=personal,
    )
