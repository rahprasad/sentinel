"""Push agent events to the investigation service's /agent-activity buffer.

Fire-and-forget — observability must never block triage. The events render
on the same dashboard panel as our investigation agents, so the harness's
triage and watcher show up alongside walker / domain-intel / synthesizer.
"""
from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Optional

import httpx
import structlog

from src.config import settings

log = structlog.get_logger("harness.activity")

_client: Optional[httpx.AsyncClient] = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=2.0)
    return _client


async def emit(
    agent: str,
    event: str,
    incident_id: Optional[str] = None,
    duration_ms: Optional[int] = None,
    **details: Any,
) -> None:
    """Push an event. Errors are swallowed — telemetry never blocks work."""
    url = f"{settings.INVESTIGATION_URL.rstrip('/')}/agent-activity/event"
    payload = {
        "agent": agent,
        "event": event,
        "incident_id": incident_id,
        "duration_ms": duration_ms,
        "details": details or None,
    }
    try:
        await _get_client().post(url, json=payload)
    except (httpx.HTTPError, asyncio.TimeoutError) as exc:
        log.debug("activity.emit_failed", agent=agent, event=event, error=str(exc))


@asynccontextmanager
async def track(
    agent: str,
    incident_id: Optional[str] = None,
    **details: Any,
) -> AsyncIterator[None]:
    """Bracket a unit of work with started/completed (or failed) events."""
    started = time.monotonic()
    await emit(agent, "started", incident_id=incident_id, **details)
    try:
        yield
    except Exception as exc:
        await emit(
            agent,
            "failed",
            incident_id=incident_id,
            duration_ms=int((time.monotonic() - started) * 1000),
            error=str(exc),
        )
        raise
    await emit(
        agent,
        "completed",
        incident_id=incident_id,
        duration_ms=int((time.monotonic() - started) * 1000),
    )
