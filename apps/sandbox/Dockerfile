# Playwright + Chromium baked in. Ephemeral container, no creds, no volumes.
FROM mcr.microsoft.com/playwright/python:v1.49.0-noble

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY src ./src

EXPOSE 8080

# Zeabur sets $PORT to the public-facing port; default to 8080 locally.
CMD uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8080}
