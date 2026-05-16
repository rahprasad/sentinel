#!/usr/bin/env python3
"""Reprocess incidents that don't have an investigation card yet.

Picks every row in either of these states:
  - status='done' AND investigation IS NULL  (Person A's seeds)
  - status='investigating'                   (anything left in the queue)

Resets each to 'investigating', invokes orchestrator.investigate() in
sequence (TokenRouter is the bottleneck — parallel calls risk rate-limit),
and prints a one-liner per row when it lands.

Run:
    apps/investigation/.venv/bin/python scripts/reprocess_pending.py
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

REPO = Path(__file__).resolve().parents[1]
load_dotenv(REPO / ".env")
sys.path.insert(0, str(REPO / "apps" / "investigation"))

from src import db as sdb  # noqa: E402
from src import orchestrator  # noqa: E402
from src.agent import app  # noqa: E402


async def main() -> int:
    pool = await sdb.connect()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id::text AS id,
                   status,
                   triage->>'scam_type' AS scam_type,
                   substr(coalesce(subject, body, ''), 1, 60) AS snippet
              FROM incidents
             WHERE (status = 'done' AND investigation IS NULL)
                OR status = 'investigating'
             ORDER BY received_at DESC
            """,
        )

    if not rows:
        print("nothing to reprocess")
        await sdb.disconnect()
        return 0

    print(f"reprocessing {len(rows)} incident(s) via {app.node_id}\n")

    failures: list[str] = []
    for i, row in enumerate(rows, start=1):
        incident_id = row["id"]
        scam_type = row["scam_type"] or "?"
        snippet = (row["snippet"] or "").replace("\n", " ")
        print(f"[{i}/{len(rows)}] {incident_id[:8]}…  {scam_type:<18}  {snippet}")

        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE incidents
                   SET status = 'investigating',
                       investigation = NULL,
                       screenshots = ARRAY[]::text[],
                       estimated_loss_usd = NULL
                 WHERE id = $1::uuid
                """,
                incident_id,
            )

        t0 = time.monotonic()
        try:
            card = await orchestrator.investigate(incident_id=incident_id)
        except Exception as exc:
            print(f"        FAIL: {exc}")
            failures.append(incident_id)
            continue
        elapsed = time.monotonic() - t0

        async with pool.acquire() as conn:
            after = await conn.fetchrow(
                """
                SELECT status, estimated_loss_usd, array_length(screenshots, 1) AS n_screens
                  FROM incidents WHERE id = $1::uuid
                """,
                incident_id,
            )
        print(
            f"        ✓ {after['status']}  ${after['estimated_loss_usd']}  "
            f"{after['n_screens'] or 0} screenshots  ({elapsed:.1f}s)  "
            f"→ {card.scam_type}"
        )

    print("\n=== summary ===")
    async with pool.acquire() as conn:
        breakdown = await conn.fetch(
            """
            SELECT status,
                   count(*) FILTER (WHERE investigation IS NOT NULL) AS with_card,
                   count(*) FILTER (WHERE investigation IS NULL) AS without_card
              FROM incidents GROUP BY status ORDER BY status
            """
        )
    for r in breakdown:
        print(f"  {r['status']:<14}  with_card={r['with_card']}  without_card={r['without_card']}")

    await sdb.disconnect()
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
