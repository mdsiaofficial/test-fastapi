# Stage 1: obtain the uv binary from the official distroless image (no pip).
# Pinned to the uv version used by the local project.
FROM ghcr.io/astral-sh/uv:0.12.3 AS uv

FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    UV_COMPILE_BYTECODE=1 \
    UV_NO_DEV=1

WORKDIR /app

# Install uv by copying the binary from the official image — no pip involved.
COPY --from=uv /uv /uvx /usr/local/bin/

# Install runtime dependencies from the lockfile first (better layer caching).
# --no-install-project: src/ isn't copied yet, so only dependencies install here
# (a full sync would fail, since building the project needs the source tree).
# README.md must be present: uv_build reads it when packaging the project.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --no-dev --frozen --no-install-project

COPY alembic.ini ./
COPY alembic ./alembic
COPY src ./src

# Now that the source tree exists, sync again to install the project itself.
RUN uv sync --no-dev --frozen

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
