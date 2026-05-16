"""Heartbeat loop — keeps harness_status rows fresh.

Every HEARTBEAT_INTERVAL seconds, updates last_check for all active
watcher sources so the dashboard can show "monitoring active".
"""

from __future__ import annotations

import asyncio

import structlog

from src.config import settings
from src.db.pool import get_pool

logger = structlog.get_logger()

# Sources managed by the harness
_HARNESS_SOURCES = ("email_imap", "email_webhook")


async def heartbeat_loop() -> None:
    """Long-running coroutine that heartbeats harness_status rows."""
    logger.info("heartbeat.started", interval=settings.HEARTBEAT_INTERVAL)

    while True:
        try:
            await _beat()
        except asyncio.CancelledError:
            logger.info("heartbeat.cancelled")
            return
        except Exception as exc:
            logger.error("heartbeat.error", error=str(exc))

        await asyncio.sleep(settings.HEARTBEAT_INTERVAL)


async def _beat() -> None:
    """Update last_check for all harness sources."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        for source in _HARNESS_SOURCES:
            await conn.execute(
                """
                INSERT INTO harness_status (source, last_check, state, items_scanned_total)
                VALUES ($1, now(), 'active', 0)
                ON CONFLICT (source) DO UPDATE
                  SET last_check = now(),
                      state = 'active'
                """,
                source,
            )
    logger.debug("heartbeat.pulse")


async def mark_source_error(source: str, error_message: str) -> None:
    """Mark a harness source as errored."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO harness_status (source, last_check, state, items_scanned_total, error_message)
            VALUES ($1, now(), 'error', 0, $2)
            ON CONFLICT (source) DO UPDATE
              SET last_check = now(),
                  state = 'error',
                  error_message = $2
            """,
            source,
            error_message[:500],
        )
    logger.warning("heartbeat.source_error", source=source, error=error_message[:80])
