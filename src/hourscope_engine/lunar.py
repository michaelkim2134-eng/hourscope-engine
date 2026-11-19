"""The Moon's daily state: phase, tithi, nakshatra, sign, void-of-course.

Void-of-course Moon: the stretch between the Moon's last exact major aspect
(conjunction, sextile, square, trine, opposition) to a planet (Sun to Pluto)
and the moment it enters the next sign. Traditionally a weak time to start
things. It is measured in the tropical zodiac, as Western calendars do.
"""

from __future__ import annotations

from dataclasses import dataclass

from .chart import NAKSHATRAS, SIGNS
from .sky import PLANET_IDS, bisect_root, longitude_of, signed_diff

# Rudhyar's eight lunar phases, each 45 degrees of Moon-Sun separation.
PHASES = ["New Moon", "Crescent", "First Quarter", "Gibbous",
          "Full Moon", "Disseminating", "Last Quarter", "Balsamic"]

TITHIS = [
    "Pratipada", "Dwitiya", "Tritiya", "Chaturthi", "Panchami", "Shashthi", "Saptami",
    "Ashtami", "Navami", "Dashami", "Ekadashi", "Dwadashi", "Trayodashi", "Chaturdashi",
]

ASPECT_ANGLES = (0.0, 60.0, 90.0, 120.0, 180.0)
_ASPECT_PLANETS = [p for p in PLANET_IDS if p != "Moon"]


@dataclass
class MoonState:
    sign: str
    sign_degree: float
    phase: str
    elongation: float        # Moon minus Sun, 0-360
    tithi_number: int        # 1-30
    tithi: str               # e.g. "Shukla Ekadashi", "Purnima", "Amavasya"
    paksha: str              # "Shukla" (waxing) or "Krishna" (waning)
    nakshatra: str | None    # Vedic only
    void_of_course: bool
    void_start_jd: float | None
    void_end_jd: float | None


def tithi_of(elongation: float) -> tuple[int, str, str]:
    n = int((elongation % 360) // 12) + 1
    paksha = "Shukla" if n <= 15 else "Krishna"
    if n == 15:
        return n, "Purnima", paksha
    if n == 30:
        return n, "Amavasya", paksha
    return n, f"{paksha} {TITHIS[(n - 1) % 15]}", paksha


def phase_of(elongation: float) -> str:
    return PHASES[int((elongation % 360) // 45)]


def _moon_sign_index(jd: float) -> int:
    return int(longitude_of("Moon", jd)[0] // 30)


def next_moon_ingress(jd: float) -> float:
    """When the Moon next enters a new (tropical) sign."""
    start = _moon_sign_index(jd)
    step = 2 / 24
    t = jd
    while _moon_sign_index(t + step) == start:
        t += step
    return bisect_root(lambda x: 0.5 if _moon_sign_index(x) == start else -0.5, t, t + step, 1e-6)


def previous_moon_ingress(jd: float) -> float:
    start = _moon_sign_index(jd)
    step = 2 / 24
    t = jd
    while _moon_sign_index(t - step) == start:
        t -= step
    return bisect_root(lambda x: 0.5 if _moon_sign_index(x) == start else -0.5, t, t - step, 1e-6)


def moon_aspect_times(start: float, end: float) -> list[tuple[float, str, float]]:
    """Exact Moon aspects (time, planet, angle) between start and end."""
    step = 1 / 24
    n = max(2, int((end - start) / step) + 2)
    times = [start + i * (end - start) / (n - 1) for i in range(n)]
    moon = [longitude_of("Moon", t)[0] for t in times]
    found: list[tuple[float, str, float]] = []
    for planet in _ASPECT_PLANETS:
        pl = [longitude_of(planet, t)[0] for t in times]
        for angle in ASPECT_ANGLES:
            targets = {angle, -angle} if angle not in (0.0, 180.0) else {angle}
            for target in targets:
                g = [signed_diff(m - p, target) for m, p in zip(moon, pl)]
                for i in range(n - 1):
                    a, b = g[i], g[i + 1]
                    if abs(a) < 30 and abs(b) < 30 and (a <= 0 < b or b <= 0 < a):
                        def f(t, planet=planet, target=target):
                            return signed_diff(longitude_of("Moon", t)[0] - longitude_of(planet, t)[0], target)
                        found.append((bisect_root(f, times[i], times[i + 1]), planet, angle))
    return sorted(found)


def void_of_course_window(jd: float) -> tuple[float, float, float]:
    """(sign_begin, void_start, void_end) for the Moon's current sign.

    The void period runs from void_start (the last exact aspect in this sign)
    to void_end (the next ingress). If the Moon makes no aspect at all in this
    sign (rare), the whole sign is void and void_start == sign_begin.
    """
    end = next_moon_ingress(jd)
    begin = previous_moon_ingress(jd)
    aspects = moon_aspect_times(begin, end)
    start = aspects[-1][0] if aspects else begin
    return begin, start, end


def void_of_course_period(jd: float) -> tuple[float, float]:
    """(start, end) of the void-of-course period in the Moon's current sign."""
    _, start, end = void_of_course_window(jd)
    return start, end


def moon_state(jd: float, sidereal: bool = False) -> MoonState:
    moon_lon = longitude_of("Moon", jd, sidereal)[0]
    elong = (longitude_of("Moon", jd)[0] - longitude_of("Sun", jd)[0]) % 360
    tnum, tname, paksha = tithi_of(elong)
    v_start, v_end = void_of_course_period(jd)
    voc = v_start <= jd < v_end
    nak = NAKSHATRAS[int(moon_lon * 27 / 360 + 1e-9) % 27] if sidereal else None
    return MoonState(
        sign=SIGNS[int(moon_lon // 30)], sign_degree=moon_lon % 30, phase=phase_of(elong),
        elongation=elong, tithi_number=tnum, tithi=tname, paksha=paksha, nakshatra=nak,
        void_of_course=voc, void_start_jd=v_start, void_end_jd=v_end,
    )


# ---------------------------------------------------------------- new and full Moons
def lunations(jd_start: float, jd_end: float, sidereal: bool = False) -> list[dict]:
    """Exact new and full Moons in [jd_start, jd_end], with the sign they fall in."""
    from .sky import datetime_from_jd

    def elong(t: float) -> float:
        return (longitude_of("Moon", t)[0] - longitude_of("Sun", t)[0]) % 360

    out: list[dict] = []
    step = 0.5
    t = jd_start
    prev = elong(t)
    while t < jd_end:
        t2 = t + step
        cur = elong(t2)
        found: tuple[str, float] | None = None
        if prev > 300 and cur < 60:  # elongation wrapped through 0: new Moon
            found = ("new", bisect_root(lambda x: signed_diff(elong(x), 0.0), t, t2, 1e-6))
        elif prev < 180 <= cur:       # crossed 180: full Moon
            found = ("full", bisect_root(lambda x: elong(x) - 180.0, t, t2, 1e-6))
        if found and jd_start <= found[1] <= jd_end:
            kind, when = found
            body = "Moon" if kind == "full" else "Sun"
            lon = longitude_of(body, when, sidereal)[0]
            out.append({"type": kind, "at": datetime_from_jd(when).isoformat(),
                        "sign": SIGNS[int(lon // 30)], "degree": round(lon % 30, 2)})
        prev, t = cur, t2
    return out
