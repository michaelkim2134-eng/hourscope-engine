"""Print a user's day: rating, theme and best hours.

Example:
    python -m hourscope_engine.today --birth-date 1990-03-14 --birth-time 15:20 \\
        --birth-place Seoul --place "New York" --date 2026-11-10 --system vedic
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, time

from .chart import compute_chart
from .daily import daily_report
from .places import find_place


def _place(name: str):
    matches = find_place(name)
    if not matches:
        raise SystemExit(f"Couldn't find '{name}'. Try a bigger nearby city.")
    return matches[0]


def _hm(iso: str) -> str:
    return datetime.fromisoformat(iso).strftime("%H:%M")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Print a Hourscope day.")
    ap.add_argument("--birth-date", required=True)
    ap.add_argument("--birth-time", help="HH:MM; leave out if unknown")
    ap.add_argument("--birth-place", required=True)
    ap.add_argument("--place", required=True, help="where the user is today")
    ap.add_argument("--date", help="YYYY-MM-DD (default: today)")
    ap.add_argument("--system", choices=["western", "vedic"], default="western")
    ap.add_argument("--all", action="store_true", help="show all 24 hours")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    bp, here = _place(args.birth_place), _place(args.place)
    birth = date.fromisoformat(args.birth_date)
    bt = time.fromisoformat(args.birth_time) if args.birth_time else None
    day = date.fromisoformat(args.date) if args.date else date.today()
    chart = compute_chart(birth, bt, bp.latitude, bp.longitude, bp.timezone, system=args.system)
    r = daily_report(chart, birth, day, here.latitude, here.longitude, here.timezone)

    print(f"\n{day:%A %d %B %Y} in {here.name} ({args.system})")
    print(f"Sunrise {_hm(r.sunrise)}  Sunset {_hm(r.sunset)}  Day ruler {r.day_ruler}")
    print(f"\nToday's energy: {r.rating}/10")
    t = r.theme
    print(f"  Personal Day {r.numerology['personal_day']}: {t['personal_day_theme']}")
    print(f"  Moon in {t['moon_sign']}, {t['moon_phase']}"
          + (f", {t['tithi']}, nakshatra {t['moon_nakshatra']}" if "tithi" in t else ""))
    if t["key_transit"]:
        print(f"  Key influence: {t['key_transit']}")
    if r.rahu_kaal:
        print(f"  Rahu Kaal: {_hm(r.rahu_kaal[0])}-{_hm(r.rahu_kaal[1])}")
    if r.moon.get("void_start"):
        print(f"  Moon void of course: {r.moon['void_start'][:16].replace('T', ' ')} to "
              f"{r.moon['void_end'][:16].replace('T', ' ')}")
    for w in r.warnings:
        print(f"  NOTE: {w}")

    print("\nBest hours:")
    for h in r.best_hours:
        print(f"  {_hm(h.start)}-{_hm(h.end)}  {h.ruler:<8} {h.score:>3}  good for {', '.join(h.good_for[:3])}")
        print(f"      why: {'; '.join(h.reasons)}")
    if r.caution_hours:
        print("\nGo easy:")
        for h in r.caution_hours:
            print(f"  {_hm(h.start)}-{_hm(h.end)}  {h.ruler:<8} {h.score:>3}  ({'; '.join(h.reasons)})")
    if args.all:
        print("\nAll planetary hours:")
        for h in r.hours:
            print(f"  {h.number:>2} {_hm(h.start)}-{_hm(h.end)}  {h.ruler:<8} {h.score:>3}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
