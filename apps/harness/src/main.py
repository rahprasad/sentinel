"""Sentinel Harness — always-on monitoring service.

Runs four concurrent coroutines:
  1. imap_watcher   — real-time email via IMAP IDLE
  2. webhook_server — FastAPI /ingest endpoint
  3. triage_worker  — classifies triaging incidents
  4. heartbeat_loop — keeps harness_status alive
"""

from __future__ import annotations

import asyncio
import logging
import signal

import structlog
import uvicorn

from src.config import settings
from src.db.pool import close_pool, get_pool

logger = structlog.get_logger()


async def _init_db() -> None:
    """Ensure connection pool is warm and tables exist."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Quick sanity check
        await conn.fetchval("SELECT count(*) FROM incidents")
    logger.info("db.ready")


async def run_harness() -> None:
    """Main harness entrypoint."""
    from src.agent import (
        app as agent_app,
        start_agentfield_registration,
        stop_agentfield_registration,
    )
    from src.triage.worker import triage_worker
    from src.watchers.heartbeat import heartbeat_loop
    from src.watchers.imap import imap_watcher
    from src.watchers.webhook import create_webhook_app

    await _init_db()
    await start_agentfield_registration(settings.HARNESS_WEBHOOK_PORT)

    # Start the AgentField app and webhook routes on the same event loop.
    webhook_app = create_webhook_app(agent_app)
    config = uvicorn.Config(
        webhook_app,
        host="0.0.0.0",
        port=settings.HARNESS_WEBHOOK_PORT,
        log_level="warning",
    )
    server = uvicorn.Server(config)
    webhook_task = asyncio.create_task(server.serve())
    logger.info("webhook.listening", port=settings.HARNESS_WEBHOOK_PORT)

    # Run the long-lived coroutines concurrently
    try:
        await asyncio.gather(
            webhook_task,
            imap_watcher(),
            triage_worker(),
            heartbeat_loop(),
        )
    finally:
        await stop_agentfield_registration()


def main() -> None:
    """CLI entrypoint."""
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    )
    logger.info("harness.starting")

    loop = asyncio.new_event_loop()

    # Graceful shutdown on SIGTERM / SIGINT
    async def _shutdown() -> None:
        logger.info("harness.shutting_down")
        await close_pool()
        loop.stop()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.ensure_future(_shutdown()))

    try:
        loop.run_until_complete(run_harness())
    except KeyboardInterrupt:
        pass
    finally:
        loop.run_until_complete(close_pool())
        loop.close()


if __name__ == "__main__":
    main()
