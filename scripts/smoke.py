#!/usr/bin/env python3
"""End-to-end smoke check for the investigation pipeline.

Inserts a synthetic 'investigating' row, waits up to N seconds for the
worker to transition it to 'done' or 'safe', and validates the resulting
card has the load-bearing fields the drawer expects.

Run from the repo root with services up:
    python scripts/smoke.py

Exit codes:
    0  card written, all required fields present
    1  timed out waiting for worker
    2  worker finished but card is malformed
    3  setup error
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import uuid

import asyncpg

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://sentinel:sentinel@localhost:5432/sentinel",
)
TIMEOUT_S = int(os.environ.get("SMOKE_TIMEOUT_S", "120"))

REQUIRED_CARD_FIELDS = ("scam_type", "what_they_sent", "what_they_wanted", "how_we_caught_it")

SAMPLE = {
    "sender": "smoke-test@example.com",
    "subject": "Smoke test — fake USPS redelivery",
    "body": (
        "Your USPS package could not be delivered due to an unpaid "
        "redelivery fee of $1.99. Pay now to reschedule: "
        "https://usps-redelivery-smoke.test/pay"
    ),
    "iocs": {"urls": ["https://usps-redelivery-smoke.test/pay"]},
    "triage": {
        "is_scam": True,
        "confidence": 0.95,
        "scam_type": "fake-support",
        "tells": [
            {"span": "usps-redelivery-smoke.test", "why": "Not a usps.com domain."},
            {"span": "$1.99", "why": "Low-friction fee designed to coax a card entry."},
        ],
        "reasoning": "Smoke test fixture.",
    },
}


async def insert_incident(conn: asyncpg.Connection) -> str:
    incident_id = str(uuid.uuid4())
    await conn.execute(
        """
        INSERT INTO incidents (
            id, received_at, source, sender, subject, body,
            iocs, triage, status
        ) VALUES ($1, now(), 'email_imap', $2, $3, $4, $5::jsonb, $6::jsonb, 'investigating')
        """,
        incident_id,
        SAMPLE["sender"],
        SAMPLE["subject"],
        SAMPLE["body"],
        json.dumps(SAMPLE["iocs"]),
        json.dumps(SAMPLE["triage"]),
    )
    return incident_id


async def wait_for_done(conn: asyncpg.Connection, incident_id: str) -> dict | None:
    deadline = time.monotonic() + TIMEOUT_S
    while time.monotonic() < deadline:
        row = await conn.fetchrow(
            "SELECT status, investigation, screenshots, estimated_loss_usd FROM incidents WHERE id = $1::uuid",
            incident_id,
        )
        if row and row["status"] in ("done", "safe"):
            return dict(row)
        await asyncio.sleep(2)
    return None


def validate_card(payload: dict) -> list[str]:
    inv = payload.get("investigation")
    if isinstance(inv, str):
        try:
            inv = json.loads(inv)
        except json.JSONDecodeError:
            return ["investigation is not valid JSON"]
    if not isinstance(inv, dict):
        return ["investigation is missing"]
    missing = [k for k in REQUIRED_CARD_FIELDS if k not in inv]
    return [f"missing field: {f}" for f in missing]


async def amain() -> int:
    try:
        conn = await asyncpg.connect(DATABASE_URL)
    except Exception as exc:
        print(f"setup: cannot connect to db ({exc})", file=sys.stderr)
        return 3

    try:
        incident_id = await insert_incident(conn)
        print(f"inserted incident {incident_id}")
        print(f"waiting up to {TIMEOUT_S}s for worker to finish...")
        result = await wait_for_done(conn, incident_id)
        if result is None:
            print("FAIL: worker did not transition incident to done/safe", file=sys.stderr)
            return 1
        print(f"worker finished: status={result['status']}, "
              f"screenshots={len(result['screenshots'] or [])}, "
              f"estimated_loss=${result['estimated_loss_usd']}")
        problems = validate_card(result)
        if problems:
            for p in problems:
                print(f"FAIL: {p}", file=sys.stderr)
            return 2
        print("OK")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(amain()))
