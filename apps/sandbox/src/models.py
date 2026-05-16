"""Sandbox API contracts."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, HttpUrl

FunnelTerminus = Literal[
    "payment_processor",
    "telegram",
    "whatsapp",
    "credentials_form",
    "unknown",
    "error",
]


class WalkRequest(BaseModel):
    url: HttpUrl
    incident_id: str = Field(default="adhoc")


class WalkStep(BaseModel):
    screenshot_url: str
    url: str
    form_fields: list[str] = Field(default_factory=list)
    page_text: str = ""


class WalkResult(BaseModel):
    steps: list[WalkStep] = Field(default_factory=list)
    final_url: str = ""
    harvested_fields: list[str] = Field(default_factory=list)
    funnel_terminus: FunnelTerminus = "unknown"
    error: Optional[str] = None
