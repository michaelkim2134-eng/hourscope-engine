"""Pythagorean numerology from the birth date (CLAUDE.md default).

Conventions (see docs/decisions.md):
- Life Path: reduce month, day and year separately, add them, reduce again.
  Master numbers 11, 22 and 33 are kept at every step.
- Personal Year / Month / Day: reduced all the way to 1-9.
  Personal Year = month + day of birth + the current year.
  Personal Month = Personal Year + current month.
  Personal Day = Personal Month + current day.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

MASTER_NUMBERS = (11, 22, 33)

# Planet linked to each number (the common Chaldean / Cheiro mapping).
# 4 and 7 belong to Uranus/Rahu and Neptune/Ketu, which rule no planetary hour.
NUMBER_PLANETS = {
    1: "Sun", 2: "Moon", 3: "Jupiter", 4: "Uranus", 5: "Mercury",
    6: "Venus", 7: "Neptune", 8: "Saturn", 9: "Mars",
}

# Short themes for Personal Day / Year numbers (used as labels; the AI phrases them).
NUMBER_THEMES = {
    1: "fresh starts and independence",
    2: "cooperation, patience and partnership",
    3: "self-expression, creativity and social life",
    4: "work, structure and foundations",
    5: "change, freedom and adventure",
    6: "love, home and responsibility",
    7: "reflection, study and inner work",
    8: "money, ambition and achievement",
    9: "completion, generosity and letting go",
    11: "intuition and inspiration",
    22: "building something big",
    33: "service and compassion",
}


def digit_sum(n: int) -> int:
    return sum(int(c) for c in str(abs(n)))


def reduce_number(n: int, keep_masters: bool = False) -> int:
    while n > 9 and not (keep_masters and n in MASTER_NUMBERS):
        n = digit_sum(n)
    return n


def life_path(birth: date) -> int:
    parts = [reduce_number(x, keep_masters=True) for x in (birth.month, birth.day, birth.year)]
    return reduce_number(sum(parts), keep_masters=True)


def personal_year(birth: date, year: int) -> int:
    return reduce_number(reduce_number(birth.month) + reduce_number(birth.day) + reduce_number(year))


def personal_month(birth: date, on: date) -> int:
    return reduce_number(personal_year(birth, on.year) + reduce_number(on.month))


def personal_day(birth: date, on: date) -> int:
    return reduce_number(personal_month(birth, on) + reduce_number(on.day))


def planet_for(number: int) -> str:
    """Planet for a number; master numbers use their reduced digit (11 -> 2)."""
    return NUMBER_PLANETS[reduce_number(number)]


@dataclass
class Numerology:
    life_path: int
    personal_year: int
    personal_month: int
    personal_day: int

    @classmethod
    def for_day(cls, birth: date, on: date) -> "Numerology":
        return cls(life_path(birth), personal_year(birth, on.year),
                   personal_month(birth, on), personal_day(birth, on))


# ---------------------------------------------------------------- full profile (name + date)
import unicodedata as _ud

# Pythagorean letter values: A J S = 1, B K T = 2, ... I R = 9.
LETTER_VALUES = {chr(ord("A") + i): (i % 9) + 1 for i in range(26)}
VOWELS = set("AEIOU")  # Y is counted as a consonant (see docs/decisions.md)
KARMIC_DEBT = (13, 14, 16, 19)


def _letters(name: str) -> list[list[str]]:
    """Split a name into words of plain A-Z letters (accents removed)."""
    plain = _ud.normalize("NFKD", name)
    plain = "".join(c for c in plain if not _ud.combining(c)).upper()
    words = []
    for word in plain.replace("-", " ").split():
        letters = [c for c in word if "A" <= c <= "Z"]
        if letters:
            words.append(letters)
    return words


def _name_number(name: str, pick) -> tuple[int, list[int]]:
    """Reduce each word separately (keeping masters), then the total. Returns (number, compound totals seen)."""
    compounds: list[int] = []
    word_totals = []
    for word in _letters(name):
        raw = sum(LETTER_VALUES[c] for c in word if pick(c))
        if raw:
            compounds.append(raw)
            word_totals.append(reduce_number(raw, keep_masters=True))
    total = sum(word_totals)
    compounds.append(total)
    return reduce_number(total, keep_masters=True), compounds


def expression_number(name: str) -> int:
    return _name_number(name, lambda c: True)[0]


def soul_urge_number(name: str) -> int:
    return _name_number(name, lambda c: c in VOWELS)[0]


def personality_number(name: str) -> int:
    return _name_number(name, lambda c: c not in VOWELS)[0]


def birthday_number(birth: date) -> int:
    return reduce_number(birth.day, keep_masters=True)


def pinnacles_and_challenges(birth: date) -> dict:
    """Four life periods (pinnacles) and their lessons (challenges), with the ages they cover."""
    m, d, y = reduce_number(birth.month), reduce_number(birth.day), reduce_number(birth.year)
    p1 = reduce_number(m + d, keep_masters=True)
    p2 = reduce_number(d + y, keep_masters=True)
    p3 = reduce_number(p1 + p2, keep_masters=True)
    p4 = reduce_number(m + y, keep_masters=True)
    c1, c2 = abs(m - d), abs(d - y)
    c3, c4 = abs(c1 - c2), abs(m - y)
    first_end = 36 - reduce_number(life_path(birth))
    ages = [(0, first_end), (first_end + 1, first_end + 9), (first_end + 10, first_end + 18), (first_end + 19, None)]
    return {
        "pinnacles": [{"number": n, "from_age": a, "to_age": b} for n, (a, b) in zip([p1, p2, p3, p4], ages)],
        "challenges": [{"number": n, "from_age": a, "to_age": b} for n, (a, b) in zip([c1, c2, c3, c4], ages)],
    }


def karmic_debts(birth: date, name: str | None) -> list[int]:
    """Karmic debt numbers (13, 14, 16, 19) found before reduction in the main numbers."""
    seen: set[int] = set()
    if birth.day in KARMIC_DEBT:
        seen.add(birth.day)
    lp_total = sum(reduce_number(x, keep_masters=True) for x in (birth.month, birth.day, birth.year))
    if lp_total in KARMIC_DEBT:
        seen.add(lp_total)
    if name:
        for pick in (lambda c: True, lambda c: c in VOWELS, lambda c: c not in VOWELS):
            seen.update(x for x in _name_number(name, pick)[1] if x in KARMIC_DEBT)
    return sorted(seen)


def letter_counts(name: str) -> dict[int, int]:
    """How many letters of the name carry each value 1-9 (the name's "intensity" grid)."""
    counts = {n: 0 for n in range(1, 10)}
    for word in _letters(name):
        for c in word:
            counts[LETTER_VALUES[c]] += 1
    return counts


def karmic_lessons(name: str) -> list[int]:
    """Numbers 1-9 that no letter of the name carries: qualities to develop."""
    return [n for n, k in letter_counts(name).items() if k == 0]


def hidden_passions(name: str) -> list[int]:
    """The number(s) carried by the most letters (all of them when tied)."""
    counts = letter_counts(name)
    top = max(counts.values())
    return [n for n, k in counts.items() if k == top] if top else []


def life_cycles(birth: date) -> list[dict]:
    """Three long cycles: formative (birth month), productive (birth day), harvest (birth year).

    Convention (docs/decisions.md): the first cycle ends with the first pinnacle
    (age 36 minus the Life Path root), the second lasts 27 years, the third runs on.
    """
    first_end = 36 - reduce_number(life_path(birth))
    numbers = [reduce_number(x, keep_masters=True) for x in (birth.month, birth.day, birth.year)]
    ages = [(0, first_end), (first_end + 1, first_end + 27), (first_end + 28, None)]
    return [{"cycle": i + 1, "number": n, "from_age": a, "to_age": b} for i, (n, (a, b)) in enumerate(zip(numbers, ages))]


def age_on(birth: date, on: date) -> int:
    return on.year - birth.year - ((on.month, on.day) < (birth.month, birth.day))


def current_period(periods: list[dict], age: int) -> dict | None:
    """The pinnacle, challenge or cycle whose age range includes `age`."""
    for p in periods:
        if p["from_age"] <= age and (p["to_age"] is None or age <= p["to_age"]):
            return p
    return None


def life_path_pair(a: int, b: int) -> tuple[int, int]:
    """Two Life Paths as a pairing key: master numbers count as their root (11 -> 2), smaller first."""
    x, y = reduce_number(a), reduce_number(b)
    return (min(x, y), max(x, y))


NUMBER_FAMILIES = {1: "1-5-7", 5: "1-5-7", 7: "1-5-7", 2: "2-4-8", 4: "2-4-8", 8: "2-4-8", 3: "3-6-9", 6: "3-6-9", 9: "3-6-9"}


def full_profile(birth: date, full_name: str | None, on: date) -> dict:
    """Everything numerology knows about a person, for the big reading."""
    lp = life_path(birth)
    out: dict = {
        "life_path": lp,
        "birthday": birthday_number(birth),
        "personal_year": personal_year(birth, on.year),
        "personal_month": personal_month(birth, on),
        "personal_day": personal_day(birth, on),
        **pinnacles_and_challenges(birth),
        "karmic_debts": karmic_debts(birth, full_name),
        "planets": {"life_path": planet_for(lp)},
        "name_used": None,
        "life_cycles": life_cycles(birth),
        "age": age_on(birth, on),
        "personal_year_ahead": [{"year": on.year + i, "number": personal_year(birth, on.year + i)} for i in range(0, 9)],
    }
    out["current"] = {
        "pinnacle": current_period(out["pinnacles"], out["age"]),
        "challenge": current_period(out["challenges"], out["age"]),
        "life_cycle": current_period(out["life_cycles"], out["age"]),
    }
    if full_name and _letters(full_name):
        expr = expression_number(full_name)
        out.update({
            "name_used": " ".join("".join(w) for w in _letters(full_name)),
            "expression": expr,
            "soul_urge": soul_urge_number(full_name),
            "personality": personality_number(full_name),
            "maturity": reduce_number(reduce_number(lp) + reduce_number(expr), keep_masters=True),
            "karmic_lessons": karmic_lessons(full_name),
            "hidden_passions": hidden_passions(full_name),
        })
        out["planets"]["expression"] = planet_for(expr)
    return out
