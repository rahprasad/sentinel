"""Stats API route — GET /stats."""

from __future__ import annotations

from fastapi import APIRouter

from src.db.queries import get_stats

router = APIRouter(tags=["stats"])


@router.get("/stats")
async def stats() -> dict:
    """Aggregate dashboard stats: blocked count, savings, scanned today."""
    return await get_stats()
