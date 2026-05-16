"""Typed contract for the triage AgentField reasoner."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TriageTell(BaseModel):
    span: str = ""
    why: str = ""


class TriageResult(BaseModel):
    is_scam: bool = False
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    scam_type: str = "none"
    tells: list[TriageTell] = Field(default_factory=list)
    reasoning: str = ""


class TriageInput(BaseModel):
    sender: str = ""
    subject: str = ""
    body: str = ""
    urls: list[str] = Field(default_factory=list)
    iocs: dict = Field(default_factory=dict)
