"""The AgentField Agent instance for the investigation tier.

`Agent` subclasses FastAPI, so this `app` object is a normal FastAPI app —
import-and-decorate from sibling modules registers reasoners / skills with
the control plane on startup.

The worker that polls Postgres for `status='investigating'` rows runs as a
FastAPI lifespan-managed background task.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

import structlog
from agentfield import Agent, AIConfig
from agentfield.connection_manager import ConnectionConfig, ConnectionManager
from agentfield.types import AgentStatus
from fastapi.middleware.cors import CORSMiddleware

from . import activity, db
from .config import settings

# ─── structured logging ─────────────────────────────────────────────────────
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
)
logging.basicConfig(level=settings.log_level.upper())
log = structlog.get_logger("investigation.agent")


async def start_agentfield_registration(port: int) -> None:
    """Register this uvicorn-hosted Agent with the AgentField control plane."""
    if app.connection_manager is not None:
        return

    app.base_url = settings.agent_callback_url or f"http://localhost:{port}"
    app._current_status = AgentStatus.READY
    app.connection_manager = ConnectionManager(
        app,
        ConnectionConfig(
            retry_interval=10.0,
            health_check_interval=30.0,
            connection_timeout=10.0,
        ),
    )
    connected = await app.connection_manager.start()
    log.info(
        "agentfield_registration_started",
        node=settings.node_id,
        connected=connected,
        base_url=app.base_url,
    )


async def stop_agentfield_registration() -> None:
    """Stop AgentField registration/heartbeat background tasks."""
    if app.connection_manager is not None:
        await app.connection_manager.stop()
        app.connection_manager = None


# ─── lifespan: DB pool + polling worker ─────────────────────────────────────
@asynccontextmanager
async def lifespan(_app: "Agent") -> AsyncIterator[None]:
    await start_agentfield_registration(8002)
    await db.connect()
    # Lazy import to dodge a circular: orchestrator → agent → lifespan → orchestrator.
    from .orchestrator import worker_loop

    task = asyncio.create_task(worker_loop(), name="investigation-worker")
    log.info(
        "investigation_started",
        node=settings.node_id,
        control_plane=settings.agentfield_server,
        synthesizer_model=settings.synthesizer_model,
        fixture_mode=settings.fixture_mode,
    )
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        await stop_agentfield_registration()
        await db.disconnect()


# ─── the Agent ──────────────────────────────────────────────────────────────
app = Agent(
    node_id=settings.node_id,
    version=settings.node_version,
    description="Walks scam URLs, looks up domain intel, synthesizes user-facing cards.",
    tags=["sentinel", "investigation"],
    agentfield_server=settings.agentfield_server,
    callback_url=settings.agent_callback_url or None,
    ai_config=AIConfig(
        model=settings.synthesizer_model,
        # Route every app.ai() call through TokenRouter. LiteLLM honours these
        # per-config overrides and passes them to the underlying provider.
        api_key=settings.tokenrouter_api_key,
        api_base=settings.tokenrouter_base_url,
        temperature=settings.synthesizer_temperature,
        timeout=settings.synthesizer_timeout_seconds,
    ),
    lifespan=lifespan,
)

# ─── CORS for the web dashboard ─────────────────────────────────────────────
# Person A's Next.js dashboard polls /agent-activity from the browser; allow
# cross-origin reads. Wide-open in dev; tighten via env var in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# ─── /agent-activity — live view of what each agent is doing ────────────────
@app.get("/agent-activity", tags=["sentinel"])
async def get_agent_activity(limit: int = 50) -> dict:
    """Recent agent events, per-agent counters, and in-flight counts.

    The web dashboard polls this every few seconds to render the live
    "agents at work" panel. Same data the AgentField control plane would
    show, surfaced directly so we don't depend on the CP being deployed.
    """
    return activity.snapshot(limit=limit)
