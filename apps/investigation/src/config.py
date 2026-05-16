"""Centralised settings.

Reads from the repo-root `.env`. Note we use LiteLLM's standard
env-var convention for LLM access — TokenRouter is OpenAI-compatible
so `OPENAI_API_KEY` + `OPENAI_API_BASE` are all AgentField needs.
"""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_repo_root() -> Path:
    """Find the checked-out repo root, falling back to the container workdir."""
    current = Path(__file__).resolve()
    for candidate in current.parents:
        if (candidate / ".env").exists() or (candidate / "docker-compose.yml").exists():
            return candidate
    return Path.cwd()


_REPO_ROOT = _find_repo_root()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_REPO_ROOT / ".env"),
        extra="ignore",
        case_sensitive=False,
    )

    # Database
    database_url: str = "postgresql://sentinel:sentinel@localhost:5432/sentinel"

    # Inter-service URLs
    sandbox_url: str = "http://localhost:8001"
    api_url: str = "http://localhost:8000"
    internal_api_key: str = ""

    # ── AgentField ───────────────────────────────────────────────────────────
    # Control plane: defaults to the FOSS image running on 8080.
    agentfield_server: str = "http://localhost:8080"
    # Optional explicit callback URL for the CP to reach us; auto-detected if blank.
    agent_callback_url: str = ""
    # node_id and version for our agent
    node_id: str = "sentinel-investigation"
    node_version: str = "0.1.0"

    # ── TokenRouter (the hackathon's LLM router) ────────────────────────────
    # TokenRouter is OpenAI-compatible. We pass key + base URL into AgentField's
    # AIConfig explicitly (instead of relying on OPENAI_* env vars) so the
    # routing intent lives in code, not in shell state.
    tokenrouter_api_key: str = ""
    tokenrouter_base_url: str = "https://api.tokenrouter.com/v1"
    synthesizer_model: str = "openai/qwen/qwen3.5-flash"
    synthesizer_agentfield_ai_enabled: bool = False
    synthesizer_temperature: float = 0.2
    synthesizer_timeout_seconds: int = 30

    # ── Bright Data ─────────────────────────────────────────────────────────
    # Used for the sandbox walker's residential-proxy upgrade, not WHOIS.
    # python-whois inside domain_intel.py handles registration lookups directly.
    bright_data_api_key: str = ""

    # ── Pipeline behaviour ──────────────────────────────────────────────────
    poll_interval_seconds: float = 1.0
    walker_timeout_seconds: int = 75
    domain_intel_timeout_seconds: int = 15
    fixture_mode: bool = False
    fixtures_dir: str = str(_REPO_ROOT / "fixtures" / "walks")

    log_level: str = "info"


settings = Settings()
