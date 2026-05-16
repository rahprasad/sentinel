"""Top-level investigation reasoner + the polling worker that drives it.

The reasoner is exposed at `/api/v1/execute/sentinel-investigation.investigate`
so Person A's harness can invoke us directly when triage flips a row to
`status='investigating'`. The polling worker is the backup path — it picks
up rows nobody pushed at us.
"""
from __future__ import annotations

import asyncio
from typing import Any, Optional

import structlog

from . import db, fixtures
from .agent import app
from .config import settings
from .domain_intel import investigate_domain
from .models import CardContract, DomainIntel, TriageResult, WalkResult
from .sandbox_client import run_walker
from .synthesizer import (
    estimated_loss_usd,
    extract_iocs,
    synthesize,
)

log = structlog.get_logger("orchestrator")


@app.reasoner(tags=["sentinel", "orchestrator"])
async def investigate(incident_id: str) -> CardContract:
    """Pull an incident, run the pipeline, persist the card. Returns the card."""
    row = await _fetch_row(incident_id)
    if row is None:
        raise ValueError(f"incident {incident_id} not found")
    return await _investigate_row(row)


async def _investigate_row(row: dict[str, Any]) -> CardContract:
    incident_id = str(row["id"])
    triage = _coerce_triage(row.get("triage"))
    body = row.get("body") or ""
    urls = ((row.get("iocs") or {}).get("urls")) or []
    target_url: Optional[str] = urls[0] if urls else None

    log.info(
        "investigation_start",
        incident_id=incident_id,
        url=target_url,
        scam_type=triage.scam_type,
        fixture_mode=settings.fixture_mode,
    )

    walker, domain = await _gather_evidence(target_url, incident_id, triage)

    card = await synthesize(
        incident_id=incident_id,
        body=body,
        triage=triage,
        domain_intel=domain,
        walker=walker,
    )

    # Use triage's canonical scam_type for deterministic computations — the
    # card's scam_type is the LLM's pretty label ("Fake Coinbase airdrop") and
    # may not match the heuristic keys ("crypto-airdrop", "romance", etc.).
    loss = estimated_loss_usd(triage.scam_type, walker)
    iocs = extract_iocs(triage.scam_type, body, walker, domain)
    screenshots = [
        step.screenshot_url for step in (walker.steps if walker else []) if step.screenshot_url
    ]

    await db.write_card(
        incident_id=incident_id,
        investigation=card.model_dump(mode="json"),
        screenshots=screenshots,
        estimated_loss_usd=loss,
    )
    await db.upsert_seen_iocs(iocs)

    log.info(
        "investigation_done",
        incident_id=incident_id,
        steps=len(screenshots),
        estimated_loss=loss,
        funnel=card.evidence.funnel_terminus,
    )
    return card


# ─── Fan-out: walker || domain-intel ────────────────────────────────────────


async def _gather_evidence(
    target_url: Optional[str], incident_id: str, triage: TriageResult
) -> tuple[Optional[WalkResult], Optional[DomainIntel]]:
    walker_task: asyncio.Future[Optional[WalkResult]]
    domain_task: asyncio.Future[Optional[DomainIntel]]

    if target_url is None:
        walker_task = asyncio.get_event_loop().create_future()
        walker_task.set_result(None)
        domain_task = walker_task  # no URL → no domain to look up either
        return None, None

    # Fixture short-circuit lives in front of the walker fan-out.
    if settings.fixture_mode:
        fixture = fixtures.load_walk(triage.scam_type)
        if fixture is not None:
            log.info("walker_fixture_used", scam_type=triage.scam_type)
            walker_result = fixture
            domain_result = await _safe(investigate_domain(target_url))
            return walker_result, domain_result

    walker_coro = run_walker(target_url, incident_id)
    domain_coro = investigate_domain(target_url)

    walker_result, domain_result = await asyncio.gather(
        _safe(walker_coro),
        _safe(domain_coro),
    )

    if isinstance(walker_result, WalkResult) and walker_result.funnel_terminus == "error":
        fixture = fixtures.load_walk(triage.scam_type)
        if fixture is not None:
            log.info(
                "walker_fixture_fallback",
                scam_type=triage.scam_type,
                error=walker_result.error,
            )
            walker_result = fixture

    return (
        walker_result if isinstance(walker_result, WalkResult) else None,
        domain_result if isinstance(domain_result, DomainIntel) else None,
    )


async def _safe(coro):
    try:
        return await coro
    except Exception as exc:
        log.warning("agent_failed", error=str(exc))
        return None


# ─── DB helpers ─────────────────────────────────────────────────────────────


async def _fetch_row(incident_id: str) -> Optional[dict[str, Any]]:
    pool = await db.connect()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, received_at, source, sender, subject, body, iocs, triage, status
              FROM incidents
             WHERE id = $1::uuid
            """,
            incident_id,
        )
    return dict(row) if row else None


def _coerce_triage(value: Any) -> TriageResult:
    if value is None:
        return TriageResult(is_scam=True, confidence=0.5, scam_type="unknown")
    if isinstance(value, TriageResult):
        return value
    try:
        return TriageResult.model_validate(value)
    except Exception:
        return TriageResult(
            is_scam=True,
            confidence=float(value.get("confidence", 0.5)) if isinstance(value, dict) else 0.5,
            scam_type=str((value or {}).get("scam_type", "unknown")) if isinstance(value, dict) else "unknown",
        )


# ─── Polling worker (FastAPI lifespan task) ─────────────────────────────────


async def worker_loop() -> None:
    """Drain `status='investigating'` rows on a poll interval."""
    while True:
        try:
            row = await db.claim_next_investigating()
        except Exception as exc:
            log.exception("worker_claim_failed", error=str(exc))
            await asyncio.sleep(2.0)
            continue

        if row is None:
            await asyncio.sleep(settings.poll_interval_seconds)
            continue

        incident_id = str(row["id"])
        try:
            await _investigate_row(row)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.exception("worker_investigation_failed", incident_id=incident_id)
            try:
                await db.mark_failed(incident_id, str(exc))
            except Exception:
                log.exception("worker_mark_failed_errored", incident_id=incident_id)
