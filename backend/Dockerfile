FROM python:3.12-slim

WORKDIR /app

# libpq + build tools for psycopg2; Playwright Chromium deps for browser fallback scraping.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install --with-deps chromium

COPY . .

ENV PORT=8000
EXPOSE 8000

# Alembic is the schema authority in production; uvicorn binds Railway's $PORT.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
