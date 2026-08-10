# Stage 1: obtain the uv binary from the official distroless image (no pip).
# Pinned to the uv version used by the local project.
FROM ghcr.io/astral-sh/uv:0.12.3 AS uv

FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    UV_COMPILE_BYTECODE=1

WORKDIR /app

# Install uv by copying the binary from the official image — no pip involved.
COPY --from=uv /uv /uvx /usr/local/bin/

# Install dependencies from the lockfile first (better layer caching).
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --frozen

COPY alembic.ini ./
COPY alembic ./alembic
COPY src ./src

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
