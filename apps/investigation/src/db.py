"""Async Postgres helpers. One global pool, opened at startup."""
from __future__ import annotations

import json
from typing import Any, Optional

import asyncpg

from .config import settings

_pool: Optional[asyncpg.Pool] = None


async def connect() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            settings.database_url,
            min_size=1,
            max_size=8,
            init=_init_connection,
        )
    return _pool


async def disconnect() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def _init_connection(conn: asyncpg.Connection) -> None:
    await conn.set_type_codec(
        "jsonb",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )


async def claim_next_investigating() -> Optional[dict[str, Any]]:
    """Pick the oldest incident with status='investigating' and return it.

    Uses SKIP LOCKED so multiple workers don't race on the same row.
    We don't flip status here — the orchestrator will set 'done' once the card is written.
    """
    pool = await connect()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, received_at, source, sender, subject, body, iocs, triage
              FROM incidents
             WHERE status = 'investigating'
             ORDER BY received_at ASC
             LIMIT 1
            FOR UPDATE SKIP LOCKED
            """
        )
        return dict(row) if row else None


async def write_card(
    incident_id: str,
    investigation: dict[str, Any],
    screenshots: list[str],
    estimated_loss_usd: int,
) -> None:
    pool = await connect()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE incidents
               SET investigation = $2,
                   screenshots = $3,
                   estimated_loss_usd = $4,
                   status = 'done'
             WHERE id = $1
            """,
            incident_id,
            investigation,
            screenshots,
            estimated_loss_usd,
        )


async def mark_failed(incident_id: str, error: str) -> None:
    """When investigation explodes, fall back to safe so the row doesn't loop."""
    pool = await connect()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE incidents
               SET status = 'safe',
                   investigation = jsonb_build_object('error', $2::text)
             WHERE id = $1
            """,
            incident_id,
            error,
        )


async def list_incidents(limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    pool = await connect()
    rows = await pool.fetch(
        """
        SELECT id, received_at, source, sender, subject, body,
               iocs, triage, status, investigation,
               screenshots, estimated_loss_usd
          FROM incidents
         ORDER BY received_at DESC
         LIMIT $1 OFFSET $2
        """,
        limit,
        offset,
    )
    return [_row_to_dict(r) for r in rows]


async def get_incident(incident_id: str) -> Optional[dict[str, Any]]:
    pool = await connect()
    row = await pool.fetchrow(
        """
        SELECT id, received_at, source, sender, subject, body,
               iocs, triage, status, investigation,
               screenshots, estimated_loss_usd
          FROM incidents
         WHERE id = $1::uuid
        """,
        incident_id,
    )
    return _row_to_dict(row) if row else None


async def get_dashboard_stats() -> dict[str, int]:
    pool = await connect()
    scanned = await pool.fetchval(
        "SELECT COALESCE(sum(items_scanned_total), 0) FROM harness_status"
    )
    blocked = await pool.fetchval(
        "SELECT count(*) FROM incidents WHERE status IN ('investigating', 'done')"
    )
    return {"blocked_count": blocked or 0, "scanned_today": scanned or 0}


async def get_monitoring_sources() -> list[dict[str, Any]]:
    pool = await connect()
    rows = await pool.fetch(
        """
        SELECT source, last_check, state, items_scanned_total, error_message
          FROM harness_status
         ORDER BY source
        """
    )
    return [
        {
            "source": r["source"],
            "last_check": r["last_check"].isoformat() if r["last_check"] else None,
            "state": r["state"],
            "items_scanned_total": r["items_scanned_total"],
            "error_message": r["error_message"],
        }
        for r in rows
    ]


def _row_to_dict(row) -> dict[str, Any]:
    if row is None:
        return {}
    d = dict(row)
    if "id" in d:
        d["id"] = str(d["id"])
    if "received_at" in d and d["received_at"]:
        d["received_at"] = d["received_at"].isoformat()
    for key in ("iocs", "triage", "investigation"):
        val = d.get(key)
        if isinstance(val, str):
            try:
                d[key] = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                pass
    if "screenshots" in d and d["screenshots"] is None:
        d["screenshots"] = []
    return d


async def upsert_seen_iocs(iocs: list[tuple[str, str, Optional[str]]]) -> None:
    """Write back discovered IOCs so triage hits the cache next time.

    Each tuple is (ioc, ioc_type, scam_type).
    """
    if not iocs:
        return
    pool = await connect()
    async with pool.acquire() as conn:
        await conn.executemany(
            """
            INSERT INTO seen_iocs (ioc, ioc_type, scam_type)
                 VALUES ($1, $2, $3)
            ON CONFLICT (ioc, ioc_type)
              DO UPDATE SET
                 last_seen = now(),
                 hit_count = seen_iocs.hit_count + 1,
                 scam_type = COALESCE(EXCLUDED.scam_type, seen_iocs.scam_type)
            """,
            iocs,
        )
