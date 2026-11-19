# Hourscope Ephemeris Engine, for Railway, Render, Fly.io or any container host.
# Build from this folder:  docker build -t hourscope-engine services/engine
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOURSCOPE_ENV=production

WORKDIR /app

# Exact, tested versions first (cached between builds), then the engine itself.
COPY requirements.lock ./
# pyswisseph has no ready-made Linux wheel for every Python version, so it's compiled here; the compiler is
# removed again in the same step to keep the image small.
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential \
 && pip install -r requirements.lock \
 && apt-get purge -y --auto-remove build-essential \
 && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-deps .

# Swiss Ephemeris data files: seas_18.se1 gives Chiron (found automatically at /app/ephe).
COPY ephe ./ephe

# Run as an unprivileged user.
RUN useradd --create-home --uid 10001 engine
USER engine

EXPOSE 8000
# Hosts set $PORT; 8000 otherwise. ENGINE_API_KEY must be set in production (the engine refuses to start without it).
# Chart maths is CPU-bound and Python runs one calculation at a time per process, so several worker processes
# are needed to serve people in parallel (load test 2026-11-18: one worker capped at ~10 day reports a second).
# Each worker uses about 175 MB. WEB_CONCURRENCY overrides the count; match it to the host's vCPUs.
CMD ["sh", "-c", "uvicorn hourscope_engine.api:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${WEB_CONCURRENCY:-4} --proxy-headers --no-server-header"]
