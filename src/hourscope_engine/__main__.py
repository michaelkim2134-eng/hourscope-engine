"""Print a chart in plain text.

Examples:
    python -m hourscope_engine --date 1879-03-14 --time 11:30 --place "Ulm, Germany"
    python -m hourscope_engine --date 1990-03-14 --place Seoul --system both
    python -m hourscope_engine --date 1961-07-01 --time 19:45 --lat 52.83 --lon 0.5
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, time

from .chart import BirthChart, compute_chart
from .places import find_place


def _print_chart(c: BirthChart) -> None:
    title = "WESTERN (tropical, Placidus)" if c.system == "western" else "VEDIC (sidereal, Lahiri, Whole Sign)"
    print(f"\n=== {title} ===")
    print(f"Local time: {c.local_time}  ({c.timezone}, {c.time_basis})")
    print(f"UTC:        {c.utc_time}")
    if c.ayanamsa is not None:
        a = c.ayanamsa
        print(f"Ayanamsa:   {int(a)}°{int(a % 1 * 60):02d}'")
    for w in c.warnings:
        print(f"NOTE: {w}")
    print()
    for p in c.planets:
        house = f"House {p.house:>2}" if p.house else ""
        retro = "R" if p.retrograde and p.name not in ("North Node", "South Node", "Rahu", "Ketu") else " "
        extra = f"{p.nakshatra} pada {p.pada} (lord {p.nakshatra_lord})" if p.nakshatra else ""
        print(f"  {p.name:<11}{p.dms:<18}{retro} {house:<9}{extra}")
    if c.ascendant:
        label = "Lagna" if c.system == "vedic" else "Ascendant"
        extra = f"{c.ascendant.nakshatra} pada {c.ascendant.pada}" if c.ascendant.nakshatra else ""
        print(f"  {label:<11}{c.ascendant.dms:<30}{extra}")
        if c.system == "western":
            print(f"  {'Midheaven':<11}{c.midheaven.dms}")
    if c.aspects:
        print("\n  Aspects:")
        for a in c.aspects:
            print(f"    {a.a} {a.kind} {a.b} (orb {a.orb}°)")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Print a Hourscope natal chart.")
    ap.add_argument("--date", required=True, help="birth date, YYYY-MM-DD")
    ap.add_argument("--time", help="birth time, HH:MM (24-hour). Leave out if unknown.")
    ap.add_argument("--place", help='birthplace, e.g. "Ulm, Germany"')
    ap.add_argument("--lat", type=float, help="latitude (north positive)")
    ap.add_argument("--lon", type=float, help="longitude (east positive)")
    ap.add_argument("--tz", help="IANA time zone, e.g. Asia/Seoul (looked up if left out)")
    ap.add_argument("--offset", type=float, help="force a UTC offset in hours, e.g. 5.5")
    ap.add_argument("--system", choices=["western", "vedic", "both"], default="both")
    args = ap.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    lat, lon, tz = args.lat, args.lon, args.tz
    if lat is None or lon is None:
        if not args.place:
            ap.error("give --place, or --lat and --lon")
        matches = find_place(args.place)
        if not matches:
            print(f"Couldn't find '{args.place}'. Try a bigger nearby city, or give --lat and --lon.")
            return 1
        m = matches[0]
        lat, lon, tz = m.latitude, m.longitude, tz or m.timezone
        print(f"Place: {m.name}, {m.admin1}, {m.country_code}  ({lat:.4f}, {lon:.4f}, {m.timezone})")
        if len(matches) > 1:
            others = "; ".join(f"{o.name}, {o.admin1}, {o.country_code}" for o in matches[1:])
            print(f"  (also matched: {others}; add the state or country to pick another)")

    d = date.fromisoformat(args.date)
    t = time.fromisoformat(args.time) if args.time else None
    systems = ["western", "vedic"] if args.system == "both" else [args.system]
    for s in systems:
        _print_chart(compute_chart(d, t, lat, lon, tz, system=s, manual_utc_offset_hours=args.offset))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
