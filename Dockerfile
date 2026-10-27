FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt pyproject.toml README.md ./
COPY src ./src
COPY alembic.ini ./
COPY alembic ./alembic
COPY data/fixture_orders.json ./data/fixture_orders.json

RUN pip install --upgrade pip && pip install -e ".[dev]" aiosqlite

RUN mkdir -p /app/data

CMD ["freelance-radar"]
