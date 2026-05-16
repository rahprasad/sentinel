"""IOC cache check — fast pre-LLM triage for known indicators.

Queries the `seen_iocs` table populated by Person B's investigation.
If any IOC from an incoming message matches a known scam, we can
resolve immediately without an LLM call.
"""

from __future__ import annotations

from typing import Optional

import structlog

from src.db.pool import get_pool

logger = structlog.get_logger()


async def check_ioc_cache(iocs: dict) -> Optional[dict]:
    """Check if any IOC in the message matches a known scam.

    Returns a triage result dict if there's a cache hit, None otherwise.
    A cache hit means: is_scam=True, confidence=0.99, scam_type from cache.
    """
    if not iocs:
        return None

    pool = await get_pool()

    # Collect all IOC values to check
    all_iocs: list[str] = []
    for key in ("urls", "phones", "wallets", "handles"):
        all_iocs.extend(iocs.get(key, []))

    if not all_iocs:
        return None

    # Query seen_iocs for any match
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT ioc, ioc_type, scam_type, hit_count
            FROM seen_iocs
            WHERE ioc = ANY($1)
            """,
            all_iocs,
        )

    if not rows:
        return None

    # Cache hit — resolve immediately
    hit = rows[0]
    scam_type = hit["scam_type"] or "other"

    # Update last_seen and bump hit_count
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE seen_iocs
            SET last_seen = now(), hit_count = hit_count + 1
            WHERE ioc = $1 AND ioc_type = $2
            """,
            hit["ioc"],
            hit["ioc_type"],
        )

    logger.info(
        "triage.cache_hit",
        ioc=hit["ioc"][:40],
        scam_type=scam_type,
        hit_count=hit["hit_count"] + 1,
    )

    return {
        "is_scam": True,
        "confidence": 0.99,
        "scam_type": scam_type,
        "tells": [{"span": hit["ioc"][:40], "why": "Previously identified scam operation"}],
        "reasoning": f"IOC '{hit['ioc'][:30]}' matches a known {scam_type} scam in our database",
    }
