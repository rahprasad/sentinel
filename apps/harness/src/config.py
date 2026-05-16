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
    TOKENROUTER_BASE_URL: str = "https://api.tokenrouter.com/v1"
    TRIAGE_MODEL: str = "openai/qwen/qwen3.5-flash"
    TRIAGE_AGENTFIELD_AI_ENABLED: bool = False
    TRIAGE_AGENTFIELD_TIMEOUT_SECONDS: float = 35.0
    TRIAGE_CONFIDENCE_THRESHOLD: float = 0.6

    # AgentField
    AGENTFIELD_SERVER: str = "http://localhost:8080"
    AGENT_CALLBACK_URL: str = ""
    HARNESS_AGENT_NODE_ID: str = "sentinel-triage"
    HARNESS_AGENT_VERSION: str = "0.1.0"
    AGENTFIELD_HANDOFF_ENABLED: bool = True

    # Inter-service
    API_URL: str = "http://localhost:8000"
    INTERNAL_API_KEY: str = ""
    INVESTIGATION_URL: str = "http://localhost:8002"

    # Harness tuning
    HARNESS_WEBHOOK_PORT: int = 8003
    TRIAGE_POLL_INTERVAL: float = 1.0
    HEARTBEAT_INTERVAL: float = 10.0
    IMAP_IDLE_TIMEOUT_SECONDS: int = 300
    IMAP_SWEEP_LOOKBACK_HOURS: int = 24
    IMAP_SWEEP_UNSEEN_ONLY: bool = True
    IMAP_STARTUP_SWEEP_ENABLED: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
