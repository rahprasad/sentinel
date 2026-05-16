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

from . import db
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


# ─── lifespan: DB pool + polling worker ─────────────────────────────────────
@asynccontextmanager
async def lifespan(_app: "Agent") -> AsyncIterator[None]:
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
