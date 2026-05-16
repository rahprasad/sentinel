#!/usr/bin/env python3
"""End-to-end pipeline test against Zeabur DB.

Calls the real orchestrator.investigate() on one of our seeded
`status='investigating'` rows. Behaviour:
  - sandbox HTTP call fails (no sandbox running locally) → fixture fallback
  - python-whois runs against the seeded scam domain (may error, that's fine)
  - synthesizer goes through AgentField → LiteLLM → TokenRouter → GLM-4.6
  - card gets persisted to incidents.investigation + status='done'

Run:
    apps/investigation/.venv/bin/python scripts/test_pipeline_e2e.py [incident_id]

Default incident_id = pig-butchering seed (33333333-...).
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO = Path(__file__).resolve().parents[1]
load_dotenv(REPO / ".env")
sys.path.insert(0, str(REPO / "apps" / "investigation"))

# Import our pipeline modules. Registers @app.skill / @app.reasoner.
from src import db as sdb  # noqa: E402
from src import orchestrator  # noqa: E402
from src.agent import app  # noqa: E402  -- ensure agent is constructed

DEFAULTS = {
    "romance": "11111111-1111-1111-1111-111111111111",
    "crypto-airdrop": "22222222-2222-2222-2222-222222222222",
    "pig-butchering": "33333333-3333-3333-3333-333333333333",
    "fake-support": "44444444-4444-4444-4444-444444444444",
}


async def main() -> int:
    incident_id = sys.argv[1] if len(sys.argv) > 1 else DEFAULTS["pig-butchering"]
    print(f"investigating {incident_id}")
    print(f"agent node_id: {app.node_id}")

    # Reset the row in case a prior run completed it.
    pool = await sdb.connect()
    async with pool.acquire() as conn:
        before = await conn.fetchrow(
            "SELECT id::text, status, triage->>'scam_type' AS scam_type FROM incidents WHERE id = $1::uuid",
            incident_id,
        )
        if before is None:
            print(f"FAIL: no row with id={incident_id}", file=sys.stderr)
            return 2
        print(f"before: status={before['status']} scam_type={before['scam_type']}")

        if before["status"] != "investigating":
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
            print("reset to status='investigating'")

    # Drive the pipeline.
    try:
        card = await orchestrator.investigate(incident_id=incident_id)
    except Exception as exc:
        import traceback; traceback.print_exc()
        print(f"FAIL: orchestrator raised: {exc}", file=sys.stderr)
        return 3

    # Verify what landed in the DB.
    async with pool.acquire() as conn:
        after = await conn.fetchrow(
            """
            SELECT status, investigation, screenshots, estimated_loss_usd
              FROM incidents WHERE id = $1::uuid
            """,
            incident_id,
        )

    await sdb.disconnect()

    print("\n=== AFTER ===")
    print(f"status:              {after['status']}")
    print(f"estimated_loss_usd:  ${after['estimated_loss_usd']}")
    print(f"screenshots:         {len(after['screenshots'] or [])}")

    inv = after["investigation"]
    if isinstance(inv, str):
        inv = json.loads(inv)
    if not inv:
        print("FAIL: investigation jsonb is empty", file=sys.stderr)
        return 4

    print(f"scam_type:           {inv.get('scam_type')}")
    print(f"what_they_wanted:    {inv.get('what_they_wanted')}")
    print(f"how_we_caught_it ({len(inv.get('how_we_caught_it') or [])} entries):")
    for entry in inv.get("how_we_caught_it") or []:
        print(f"  - [{entry.get('agent')}] {entry.get('finding')}")
    print(f"how_to_spot_it ({len(inv.get('how_to_spot_it') or [])}):")
    for rule in inv.get("how_to_spot_it") or []:
        print(f"  • {rule}")
    print(f"funnel_terminus:     {inv.get('evidence', {}).get('funnel_terminus')}")
    print(f"harvested_fields:    {inv.get('evidence', {}).get('harvested_fields')}")

    print("\nOK")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
