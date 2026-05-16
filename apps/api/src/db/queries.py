"""Async query functions for the API service."""

from __future__ import annotations

import json
from typing import Optional

from src.db.pool import get_pool


async def get_incidents(limit: int = 50, offset: int = 0) -> list[dict]:
    """Fetch incidents newest-first."""
    pool = await get_pool()
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


async def get_incident(incident_id: str) -> Optional[dict]:
    """Fetch a single incident by ID."""
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        SELECT id, received_at, source, sender, subject, body,
               iocs, triage, status, investigation,
               screenshots, estimated_loss_usd
        FROM incidents
        WHERE id = $1
        """,
        incident_id,
    )
    return _row_to_dict(row) if row else None


async def get_stats() -> dict:
    """Aggregate dashboard stats."""
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        SELECT
            count(*) FILTER (WHERE status IN ('investigating', 'done')) AS blocked_count,
            COALESCE(sum(estimated_loss_usd) FILTER (WHERE status IN ('investigating', 'done')), 0) AS estimated_savings_usd,
            COALESCE(sum(items_scanned_total), 0) AS scanned_today
        FROM incidents, (SELECT sum(items_scanned_total) AS items_scanned_total
                         FROM harness_status) AS hs
        """
    )

    # Also compute scanned_today separately for clarity
    scanned = await pool.fetchval(
        "SELECT COALESCE(sum(items_scanned_total), 0) FROM harness_status"
    )

    blocked = await pool.fetchval(
        "SELECT count(*) FROM incidents WHERE status IN ('investigating', 'done')"
    )

    savings = await pool.fetchval(
        "SELECT COALESCE(sum(estimated_loss_usd), 0) FROM incidents WHERE status IN ('investigating', 'done')"
    )

    return {
        "blocked_count": blocked or 0,
        "estimated_savings_usd": savings or 0,
        "scanned_today": scanned or 0,
    }


async def get_monitoring() -> list[dict]:
    """Fetch all harness_status rows for the monitoring UI."""
    pool = await get_pool()
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


def _row_to_dict(row) -> dict:
    """Convert an asyncpg Record to a JSON-friendly dict."""
    d = dict(row)
    # Convert UUID to string
    if "id" in d:
        d["id"] = str(d["id"])
    # Convert datetime to ISO string
    if "received_at" in d and d["received_at"]:
        d["received_at"] = d["received_at"].isoformat()
    # Convert jsonb to dict
    for key in ("iocs", "triage", "investigation"):
        val = d.get(key)
        if isinstance(val, str):
            try:
                d[key] = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                pass
    # Convert text[] to list
    if "screenshots" in d and d["screenshots"] is None:
        d["screenshots"] = []
    return d
