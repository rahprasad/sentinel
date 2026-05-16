"""Incidents API routes — GET /incidents, GET /incidents/{id}."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from src.db.queries import get_incident, get_incidents

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.get("")
async def list_incidents(limit: int = 50, offset: int = 0) -> dict:
    """List incidents newest-first."""
    incidents = await get_incidents(limit=limit, offset=offset)
    return {"incidents": incidents, "count": len(incidents)}


@router.get("/{incident_id}")
async def get_single_incident(incident_id: str) -> dict:
    """Fetch a single incident by ID."""
    incident = await get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident
