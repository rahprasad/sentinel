"""AgentField node for Sentinel's detection tier.

The harness remains the always-on process, but triage is exposed as an
AgentField reasoner and scam handoff is routed to the investigation agent
through the control plane when available.
"""

from __future__ import annotations

import structlog
from agentfield import Agent, AIConfig
from agentfield.connection_manager import ConnectionConfig, ConnectionManager
from agentfield.types import AgentStatus

from src.config import settings
from src.triage.models import TriageInput, TriageResult

logger = structlog.get_logger("triage.agent")


app = Agent(
    node_id=settings.HARNESS_AGENT_NODE_ID,
    version=settings.HARNESS_AGENT_VERSION,
    description="Classifies suspicious messages and hands scam incidents to investigation.",
    tags=["sentinel", "detection", "triage"],
    agentfield_server=settings.AGENTFIELD_SERVER,
    callback_url=settings.AGENT_CALLBACK_URL or None,
    ai_config=AIConfig(
        model=settings.TRIAGE_MODEL,
        api_key=settings.TOKENROUTER_API_KEY,
        api_base=settings.TOKENROUTER_BASE_URL,
        temperature=0.1,
        timeout=30,
    ),
)


async def start_agentfield_registration(port: int) -> None:
    """Register this uvicorn-hosted Agent with the AgentField control plane."""
    if app.connection_manager is not None:
        return

    app.base_url = settings.AGENT_CALLBACK_URL or f"http://localhost:{port}"
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
    logger.info(
        "agentfield.registration_started",
        node_id=settings.HARNESS_AGENT_NODE_ID,
        connected=connected,
        base_url=app.base_url,
    )


async def stop_agentfield_registration() -> None:
    """Stop AgentField registration/heartbeat background tasks."""
    if app.connection_manager is not None:
        await app.connection_manager.stop()
        app.connection_manager = None


@app.reasoner(tags=["sentinel", "triage"])
async def triage_message(payload: TriageInput) -> dict:
    """Classify one normalized message and return the triage JSON contract."""
    from src.triage.classify import classify_with_llm

    result = await classify_with_llm(
        sender=payload.sender,
        subject=payload.subject,
        body=payload.body,
        urls=payload.urls,
        iocs=payload.iocs,
    )
    return TriageResult.model_validate(result).model_dump()


async def dispatch_investigation(incident_id: str) -> None:
    """Best-effort AgentField handoff to Person B's investigation reasoner."""
    if not settings.AGENTFIELD_HANDOFF_ENABLED:
        return

    try:
        await app.call(
            "sentinel-investigation.investigate",
            incident_id=incident_id,
        )
        logger.info("investigation_handoff_dispatched", incident_id=incident_id)
    except Exception as exc:
        # Investigation has a DB polling fallback for status='investigating'.
        logger.warning(
            "investigation_handoff_fallback_to_polling",
            incident_id=incident_id,
            error=str(exc),
        )
