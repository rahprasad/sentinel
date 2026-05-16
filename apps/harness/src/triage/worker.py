"""Triage worker — processes incidents with status='triaging'.

Loops every TRIAGE_POLL_INTERVAL seconds, picks the oldest triaging
incident, runs pre-LLM checks then LLM classification, and updates
the incident row.
"""

from __future__ import annotations

import asyncio
import json

import structlog

from src.config import settings
from src.db.pool import get_pool
from src.triage.classify import classify_with_llm
from src.triage.ioc_cache import check_ioc_cache

logger = structlog.get_logger()


async def triage_worker() -> None:
    """Long-running coroutine that triages incidents one at a time."""
    logger.info("triage_worker.started", interval=settings.TRIAGE_POLL_INTERVAL)

    while True:
        try:
            await _process_one()
        except asyncio.CancelledError:
            logger.info("triage_worker.cancelled")
            return
        except Exception as exc:
            logger.error("triage_worker.error", error=str(exc))

        await asyncio.sleep(settings.TRIAGE_POLL_INTERVAL)


async def _process_one() -> None:
    """Pick the oldest triaging incident and classify it."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        # Atomically claim the oldest triaging row
        row = await conn.fetchrow(
            """
            UPDATE incidents
            SET status = 'triaging'  -- keep status, just lock the row
            WHERE id = (
                SELECT id FROM incidents
                WHERE status = 'triaging'
                ORDER BY received_at ASC
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            RETURNING id, sender, subject, body, iocs
            """
        )

    if row is None:
        return  # Nothing to triage

    incident_id = row["id"]
    sender = row["sender"] or ""
    subject = row["subject"] or ""
    body = row["body"] or ""
    iocs = row["iocs"] if isinstance(row["iocs"], dict) else json.loads(row["iocs"] or "{}")

    logger.info(
        "triage_worker.processing",
        incident_id=str(incident_id),
        sender=sender[:40],
        subject=subject[:60],
    )

    # Step 1: Fast IOC cache check
    cache_result = await check_ioc_cache(iocs)

    if cache_result is not None:
        triage_result = cache_result
        logger.info("triage_worker.cache_hit", incident_id=str(incident_id))
    else:
        # Step 2: LLM classification
        urls = iocs.get("urls", [])
        triage_result = await classify_with_llm(sender, subject, body, urls, iocs)
        logger.info("triage_worker.llm_done", incident_id=str(incident_id))

    # Determine new status
    is_scam = triage_result.get("is_scam", False)
    new_status = "investigating" if is_scam else "safe"

    # Update the incident
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE incidents
            SET triage = $1::jsonb,
                status = $2
            WHERE id = $3
            """,
            json.dumps(triage_result),
            new_status,
            incident_id,
        )

    logger.info(
        "triage_worker.classified",
        incident_id=str(incident_id),
        status=new_status,
        scam_type=triage_result.get("scam_type"),
        confidence=triage_result.get("confidence"),
    )
