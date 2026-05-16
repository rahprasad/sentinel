"""Sandbox-walker skill.

The sandbox is its own Zeabur service (Playwright + Chromium). From our
perspective the call is deterministic input-in / output-out, so it lives
as `@app.skill()`. Failures collapse to a WalkResult with `error` set —
the orchestrator handles the fixture fallback.
"""
from __future__ import annotations

import httpx
import structlog

from .agent import app
from .config import settings
from .models import WalkResult

log = structlog.get_logger("sandbox_client")


@app.skill(tags=["sentinel", "sandbox-walker"])
async def run_walker(url: str, incident_id: str) -> WalkResult:
    """POST to the sandbox /walk endpoint."""
    payload = {"url": url, "incident_id": incident_id}
    timeout = float(settings.walker_timeout_seconds)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{settings.sandbox_url.rstrip('/')}/walk",
                json=payload,
            )
            resp.raise_for_status()
            return WalkResult.model_validate(resp.json())
    except httpx.HTTPError as exc:
        log.warning("sandbox_http_error", incident_id=incident_id, error=str(exc))
        return WalkResult(funnel_terminus="error", error=str(exc))
    except Exception as exc:
        log.exception("sandbox_unhandled", incident_id=incident_id, error=str(exc))
        return WalkResult(funnel_terminus="error", error=str(exc))
