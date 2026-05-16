"""Sentinel API — FastAPI service serving the dashboard.

Exposes endpoints for incidents, stats, and monitoring status.
Reads from the same Postgres as the harness.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.db.pool import close_pool, get_pool
from src.routes import incidents, monitoring, stats

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB pool. Shutdown: close it."""
    await get_pool()
    logger.info("api.started")
    yield
    await close_pool()
    logger.info("api.stopped")


app = FastAPI(
    title="Sentinel API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow the Next.js dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(incidents.router)
app.include_router(stats.router)
app.include_router(monitoring.router)


@app.get("/health")
async def health() -> dict:
    """Health check endpoint."""
    return {"status": "ok"}
