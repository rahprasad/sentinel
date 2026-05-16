"""Webhook receiver — small FastAPI for manual ingest via curl.

Provides POST /ingest so the demo can be triggered even when
IMAP isn't available.  Also used for the screenshot stretch.
"""

from __future__ import annotations

import json

import structlog
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from src.config import settings
from src.db.pool import get_pool
from src.normalize.envelope import normalize_envelope

logger = structlog.get_logger()


class IngestPayload(BaseModel):
    """Payload for the /ingest endpoint."""
    sender: str
    subject: str
    body: str
    source: str = "email_webhook"


def _verify_key(api_key: str | None) -> None:
    """Validate internal API key if configured."""
    if settings.INTERNAL_API_KEY and api_key != settings.INTERNAL_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


def create_webhook_app() -> FastAPI:
    """Build and return the FastAPI application."""
    app = FastAPI(title="Sentinel Harness — Webhook Receiver")

    @app.post("/ingest")
    async def ingest(
        payload: IngestPayload,
        x_internal_key: str | None = Header(default=None),
    ) -> dict:
        """Ingest a message via webhook, normalize, and insert."""
        _verify_key(x_internal_key)
        envelope = normalize_envelope(payload.model_dump())
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO incidents (source, sender, subject, body, iocs, status)
                VALUES ($1, $2, $3, $4, $5, 'triaging')
                """,
                envelope["source"],
                envelope["sender"],
                envelope["subject"],
                envelope["body"],
                json.dumps(envelope["iocs"]),
            )
            # Bump scanned counter for this source
            await conn.execute(
                """
                INSERT INTO harness_status (source, last_check, state, items_scanned_total)
                VALUES ($1, now(), 'active', 1)
                ON CONFLICT (source) DO UPDATE
                  SET last_check = now(),
                      items_scanned_total = harness_status.items_scanned_total + 1,
                      state = 'active'
                """,
                envelope["source"],
            )

        logger.info(
            "webhook.ingested",
            source=envelope["source"],
            sender=envelope["sender"][:40],
        )
        return {"status": "ok", "source": envelope["source"]}

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    return app
