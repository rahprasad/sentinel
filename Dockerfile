# Root Dockerfile so `zeabur deploy` builds the investigation service by default.
# (Zeabur's monorepo detection picks up apps/web/package.json first otherwise.)
# Person A's harness/api/web services should each use their own per-service
# zbpack.<name>.json or be deployed via dashboard.

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY apps/investigation/requirements.txt .
RUN pip install -r requirements.txt

COPY apps/investigation/src ./src
COPY apps/investigation/prompts ./prompts
# Bake demo fixtures into the image so walker errors gracefully fall back to
# the recorded walks instead of producing zero-screenshot cards on Zeabur.
COPY fixtures ./fixtures

EXPOSE 8080

# Zeabur sets $PORT to the public-facing port; default to 8080 locally.
CMD uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8080}
