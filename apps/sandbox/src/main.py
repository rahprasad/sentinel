"""Sandbox walker FastAPI service.

One real endpoint: POST /walk. A small /screenshots/* mount serves locally
saved PNGs when S3 isn't configured — useful for dev and demos.
"""
from __future__ import annotations

import logging
from pathlib import Path

import structlog
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from .config import settings
from .models import WalkRequest, WalkResult
from .storage import local_file_for
from .walker import walk

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
)
logging.basicConfig(level=settings.log_level.upper())

app = FastAPI(title="Sentinel Sandbox", version="0.1.0")
log = structlog.get_logger("sandbox.main")


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/walk", response_model=WalkResult)
async def walk_endpoint(req: WalkRequest) -> WalkResult:
    log.info("walk_request", url=str(req.url), incident_id=req.incident_id)
    result = await walk(str(req.url), req.incident_id)
    log.info(
        "walk_complete",
        incident_id=req.incident_id,
        steps=len(result.steps),
        terminus=result.funnel_terminus,
        error=result.error,
    )
    return result


@app.get("/screenshots/{path:path}")
async def serve_screenshot(path: str) -> FileResponse:
    """Local-mode screenshot static serving. In prod these come from S3 directly."""
    file_path = local_file_for(path)
    if file_path is None or not file_path.exists():
        raise HTTPException(status_code=404, detail="not found")
    return FileResponse(file_path, media_type="image/png")


# Make sure the local screenshot dir exists at startup so /screenshots returns 404s
# rather than 500s when nothing has been walked yet.
Path(settings.local_screenshot_dir).mkdir(parents=True, exist_ok=True)
