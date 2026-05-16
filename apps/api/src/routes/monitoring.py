"""Monitoring API route — GET /monitoring."""

from __future__ import annotations

from fastapi import APIRouter

from src.db.queries import get_monitoring

router = APIRouter(tags=["monitoring"])


@router.get("/monitoring")
async def monitoring() -> dict:
    """Fetch harness status for the monitoring UI."""
    sources = await get_monitoring()
    return {"sources": sources}
