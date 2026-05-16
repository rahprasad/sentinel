FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY src ./src
COPY prompts ./prompts

# Webhook receiver port (the rest of the harness has no HTTP surface)
EXPOSE 8003

CMD ["python", "-m", "src.main"]
