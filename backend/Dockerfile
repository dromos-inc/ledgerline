# Self-hosted + cloud tier container image.
#
# Multi-stage: build in a slim image with gcc (some deps compile on install),
# then copy into a distroless-ish runtime image without build tools.

ARG PYTHON_VERSION=3.12-slim-bookworm

# ---------------------------------------------------------------------------
# Build stage
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION} AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

COPY backend/pyproject.toml ./
COPY backend/README.md ./
COPY backend/app ./app

RUN python -m venv /venv \
    && /venv/bin/pip install --upgrade pip \
    && /venv/bin/pip install .

# ---------------------------------------------------------------------------
# Runtime stage
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION} AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/venv/bin:$PATH"

# Non-root user
RUN groupadd -r ledgerline && useradd -r -g ledgerline -m -d /home/ledgerline ledgerline \
    && mkdir -p /data \
    && chown ledgerline:ledgerline /data

COPY --from=builder /venv /venv
COPY backend/app /srv/app
COPY backend/pyproject.toml /srv/

WORKDIR /srv

USER ledgerline

EXPOSE 8787

CMD ["python", "-m", "app.main"]
