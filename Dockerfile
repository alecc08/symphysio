# syntax=docker/dockerfile:1

# ---------- Stage 1: compile the React PWA ----------
FROM node:24-alpine AS frontend
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---------- Stage 2: slim Python runtime ----------
FROM python:3.15-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Dependencies first so this layer caches across app changes.
COPY backend/pyproject.toml backend/uv.lock ./
COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /usr/local/bin/uv
RUN uv sync --frozen --no-dev --no-install-project

COPY backend/app ./app
COPY backend/migrations ./migrations
COPY --from=frontend /src/frontend/dist ./static

# The version of record travels with the image: app/main.py reads this file, and
# build.yml passes --build-arg VERSION, so the OCI label, the OpenAPI document and
# the git tag are the same string.
ARG VERSION=0.0.0+unknown
COPY VERSION ./VERSION
LABEL org.opencontainers.image.title="Symphysio" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.licenses="MIT"

# Non-root, and nothing but /data is writable.
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin symphysio \
    && mkdir -p /data \
    && chown -R 10001:10001 /app /data

USER 10001

ENV SYPHYSIO_DATA_DIR=/data \
    SYPHYSIO_DB_PATH=/data/symphysio.sqlite \
    SYPHYSIO_STATIC_DIR=/app/static \
    SYPHYSIO_MIGRATIONS_DIR=/app/migrations \
    SYPHYSIO_COOKIE_SECURE=1

EXPOSE 8000

# The address here has to match the ENTRYPOINT below: a healthcheck that probes
# the wrong port reports every container unhealthy.
HEALTHCHECK --interval=30s --timeout=4s --start-period=10s \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz')"]

# Run uvicorn straight from the venv: no uv at runtime, no writes outside /data.
#
# --no-access-log: uvicorn's request line would record the email-confirmation
# link the browser opens (`GET /verify?token=…`), putting a live token in
# `docker logs` and whatever collects them. The API itself is POST/JSON, so what
# is lost is request timing noise; the reverse proxy in front is the right place
# to log traffic - and it should mask the `token` parameter (see
# docs/DEPLOYING.md).
ENTRYPOINT ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
