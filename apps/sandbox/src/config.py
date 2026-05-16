"""Sandbox config. Reads repo-root .env."""
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

    # Walker behaviour
    walker_max_steps: int = 5
    walker_timeout_seconds: int = 60
    walker_user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )

    # Bright Data Scraping Browser. When set, Playwright connects to Bright Data's
    # remote Chromium over CDP and gets residential IPs + anti-bot evasion per
    # walk. Get the wss:// URL from Bright Data dashboard → Scraping Browser →
    # Access parameters. Leave blank to use local Chromium.
    bright_data_browser_ws: str = ""

    # S3-compatible object storage (Zeabur object storage works)
    s3_endpoint: str = ""
    s3_region: str = "auto"
    s3_bucket: str = "sentinel-screenshots"
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_public_url_prefix: str = ""

    # Local fallback for screenshots when S3 isn't configured
    local_screenshot_dir: str = "/tmp/sentinel-screenshots"
    local_screenshot_url_prefix: str = "http://localhost:8001/screenshots"

    # Actionbook is exposed over MCP (Streamable HTTP). Open beta — no API key.
    # Blank disables the lookup entirely; the walker keeps its heuristic fallback.
    actionbook_mcp_url: str = "https://edge.actionbook.dev/mcp"
    actionbook_timeout_seconds: float = 4.0

    log_level: str = "info"


settings = Settings()
