#!/usr/bin/env python3
"""Record sandbox walker output to fixture files.

Usage:
    python scripts/record_fixtures.py --scam-type romance --url https://...
    python scripts/record_fixtures.py --from-seeds

The first form drives a single walk. The second reads URLs out of
`db/seeds/incidents.sql` (one URL per scam_type) and records all four
fixtures in parallel.

Output: `fixtures/walks/{scam_type}.json` — the same shape the orchestrator
loads at investigation time.

Designed to run against a live sandbox at $SANDBOX_URL (default http://localhost:8001).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = ROOT / "fixtures" / "walks"
SEEDS_FILE = ROOT / "db" / "seeds" / "incidents.sql"
DEFAULT_SANDBOX = os.environ.get("SANDBOX_URL", "http://localhost:8001")
DEFAULT_TIMEOUT = float(os.environ.get("WALKER_TIMEOUT_SECONDS", "120"))


async def walk(client: httpx.AsyncClient, url: str, incident_id: str, sandbox: str) -> dict:
    resp = await client.post(
        f"{sandbox.rstrip('/')}/walk",
        json={"url": url, "incident_id": incident_id},
        timeout=DEFAULT_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


async def record_one(scam_type: str, url: str, sandbox: str) -> Path:
    print(f"  walking  {scam_type:<16}  {url}", flush=True)
    async with httpx.AsyncClient() as client:
        data = await walk(client, url, incident_id=f"fixture-{scam_type}", sandbox=sandbox)
    out = FIXTURES_DIR / f"{scam_type}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2))
    print(f"  saved    {out.relative_to(ROOT)}", flush=True)
    return out


def parse_seed_pairs() -> list[tuple[str, str]]:
    """Extract (scam_type, first_url) pairs from db/seeds/incidents.sql."""
    if not SEEDS_FILE.exists():
        return []
    text = SEEDS_FILE.read_text()
    blocks = re.split(r"^INSERT INTO incidents", text, flags=re.MULTILINE)
    pairs: list[tuple[str, str]] = []
    for block in blocks:
        # Pull first URL out of urls[] and scam_type field.
        url_match = re.search(r'"urls":\s*\[\s*"([^"]+)"', block)
        scam_match = re.search(r'"scam_type":\s*"([^"]+)"', block)
        if url_match and scam_match:
            pairs.append((scam_match.group(1), url_match.group(1)))
    # Dedup, keep first occurrence
    seen: set[str] = set()
    unique: list[tuple[str, str]] = []
    for st, url in pairs:
        if st in seen:
            continue
        seen.add(st)
        unique.append((st, url))
    return unique


async def amain(args: argparse.Namespace) -> int:
    pairs: list[tuple[str, str]] = []
    if args.from_seeds:
        pairs = parse_seed_pairs()
        if not pairs:
            print("no seed (scam_type, url) pairs found", file=sys.stderr)
            return 1
    elif args.scam_type and args.url:
        pairs = [(args.scam_type, args.url)]
    else:
        print("provide --from-seeds or both --scam-type and --url", file=sys.stderr)
        return 2

    print(f"recording {len(pairs)} fixture(s) via sandbox at {args.sandbox}")
    results = await asyncio.gather(
        *(record_one(st, url, args.sandbox) for st, url in pairs),
        return_exceptions=True,
    )
    failures = [r for r in results if isinstance(r, Exception)]
    if failures:
        for f in failures:
            print(f"  FAIL  {f}", file=sys.stderr)
        return 3
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Record walker fixtures.")
    parser.add_argument("--scam-type", help="canonical scam type, e.g. romance")
    parser.add_argument("--url", help="URL to walk")
    parser.add_argument(
        "--from-seeds",
        action="store_true",
        help="record fixtures for every (scam_type, url) pair in db/seeds/incidents.sql",
    )
    parser.add_argument(
        "--sandbox",
        default=DEFAULT_SANDBOX,
        help=f"sandbox base URL (default {DEFAULT_SANDBOX})",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(amain(args)))


if __name__ == "__main__":
    main()
