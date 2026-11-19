# Swiss Ephemeris data files

- `seas_18.se1`: the main asteroids, including **Chiron**, for 1800-2399 (from the official Swiss Ephemeris
  repository, github.com/aloistr/swisseph, downloaded 2026-11-14). The engine finds it here in development and at
  `/app/ephe` in the container; no setting needed. Without it, charts simply leave Chiron out.

The planets don't need any files: the engine uses the built-in Moshier model (well under an arcminute of error).
If you ever add the planet files too, point `HOURSCOPE_EPHE_PATH` at the folder that holds them.

These files are covered by the Swiss Ephemeris licence (AGPL or the Professional License).
