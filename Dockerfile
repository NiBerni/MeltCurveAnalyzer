# syntax=docker/dockerfile:1
FROM python:3.14-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .

RUN uv sync --frozen --no-dev

RUN useradd --create-home --shell /bin/bash lims_user \
    && chown -R lims_user:lims_user /app

USER lims_user

EXPOSE 8000

CMD ["sh", "-c", "python -m app.db.seed && gunicorn wsgi:app --bind 0.0.0.0:8000 --workers 4 --timeout 120 --access-logfile -"]