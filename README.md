# Hourscope Ephemeris Engine

The calculator behind [Hourscope](https://hourscope.co). It turns a birth date, time and place into a
Western (tropical) and a Vedic (sidereal) natal chart, and computes transits, Moon phases, planetary hours,
numerology and the day and timing scores the app shows. All positions come from the Swiss Ephemeris.

This is the source code of the engine that runs on hourscope.co, published under the
**GNU Affero General Public License v3** (see `LICENSE`), as the Swiss Ephemeris licence requires.
The Hourscope website, its interpretation texts and its AI prompts are a separate program and are not part
of this repository. Code comments that point to `docs/...` refer to notes in that private repository.

## Setup

Needs Python 3.11+ and a C compiler for `pyswisseph` (on Windows, Microsoft C++ Build Tools).

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]" uvicorn     # Windows
# .venv/bin/python -m pip install -e ".[dev]" uvicorn       # macOS / Linux
```

## Print a chart

```bash
python -m hourscope_engine --date 1879-03-14 --time 11:30 --place "Ulm, Germany"
```

Options: `--system western|vedic|both`, leave out `--time` if unknown,
use `--lat`/`--lon` for small towns not in the place list, `--offset` to
force a UTC offset from a birth certificate.

## Print a person's day

```bash
python -m hourscope_engine.today --birth-date 1990-03-14 --birth-time 15:20 --birth-place Seoul --place "New York" --date 2026-11-10 --system vedic
```

Add `--all` to see all 24 planetary hours.

## Run the tests

```bash
python -m pytest
```

The tests compare charts against published reference charts and against an independent calculation with
the VSOP87/ELP2000 models (via PyMeeus).

## Run the API

```bash
python -m uvicorn hourscope_engine.api:app --reload
```

Then open http://127.0.0.1:8000/docs. In production set `HOURSCOPE_ENV=production` and `ENGINE_API_KEY`;
callers must then send the key in the `X-Engine-Key` header. A `Dockerfile` is included.

## Files

- `src/hourscope_engine/timeconv.py`: local birth time to UTC with historical time zone rules
- `src/hourscope_engine/places.py`: offline city lookup and time zone from coordinates
- `src/hourscope_engine/chart.py`: planets, houses, aspects, nakshatras
- `src/hourscope_engine/hours.py`: sunrise-based planetary hours and Rahu Kaal
- `src/hourscope_engine/lunar.py`: Moon phase, tithi, nakshatra, void-of-course
- `src/hourscope_engine/numerology.py`: Pythagorean numerology and personal cycles
- `src/hourscope_engine/daily.py`: daily rating, theme and best hours
- `src/hourscope_engine/electional.py`: ranked windows for an activity ("Power Days")
- `ephe/`: Swiss Ephemeris asteroid file for Chiron (see `ephe/README.md`)
- `tests/`: reference charts, sky checks, Vedic checks, time zone cases

## Licence

Copyright (C) 2026 Hourscope. This program is free software: you can redistribute it and/or modify it under
the terms of the GNU Affero General Public License as published by the Free Software Foundation, version 3.
It is distributed WITHOUT ANY WARRANTY; see `LICENSE` for details.

Swiss Ephemeris is copyright Astrodienst AG and is used under the AGPL; `pyswisseph` is its Python binding.
