"""Harness service configuration — reads environment variables via pydantic-settings."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """All env vars the harness reads.  Falls back to .env file via
    pydantic-settings' built-in dotenv support."""

    # Database
    DATABASE_URL: str = "postgresql://sentinel:sentinel@localhost:5432/sentinel"

    # IMAP watcher
    IMAP_HOST: str = "imap.gmail.com"
    IMAP_PORT: int = 993
    IMAP_USERNAME: str = ""
    IMAP_PASSWORD: str = ""
    IMAP_MAILBOX: str = "INBOX"

    # Fallback scam-feed watcher
    SCAM_FEED_URL: str = ""
    SCAM_FEED_POLL_SECONDS: int = 30

    # TokenRouter / LLM
    TOKENROUTER_API_KEY: str = ""
    TOKENROUTER_BASE_URL: str = "https://api.tokenrouter.io/v1"
    TRIAGE_MODEL: str = "qwen-flash"
    TRIAGE_CONFIDENCE_THRESHOLD: float = 0.6

    # Inter-service
    API_URL: str = "http://localhost:8000"
    INTERNAL_API_KEY: str = ""

    # Harness tuning
    HARNESS_WEBHOOK_PORT: int = 8003
    TRIAGE_POLL_INTERVAL: float = 1.0
    HEARTBEAT_INTERVAL: float = 10.0

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
