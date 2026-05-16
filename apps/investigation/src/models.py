"""Pydantic models for the investigation pipeline.

The card contract here MUST stay aligned with the JSON the synthesizer prompt
emits and the TypeScript types the drawer consumes (`apps/web/src/lib/types.ts`).
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

AgentTag = Literal["triage", "domain-intel", "sandbox-walker"]


# ─── Inputs from the detection tier ──────────────────────────────────────────


class IOCs(BaseModel):
    urls: list[str] = Field(default_factory=list)
    phones: list[str] = Field(default_factory=list)
    wallets: list[str] = Field(default_factory=list)
    handles: list[str] = Field(default_factory=list)


class Tell(BaseModel):
    span: str
    why: str


class TriageResult(BaseModel):
    is_scam: bool
    confidence: float
    scam_type: str
    tells: list[Tell] = Field(default_factory=list)
    reasoning: str = ""


# ─── Walker output (mirrors sandbox service's WalkResult) ────────────────────


class WalkStep(BaseModel):
    screenshot_url: str
    url: str
    form_fields: list[str] = Field(default_factory=list)
    page_text: str = ""


FunnelTerminus = Literal[
    "payment_processor",
    "telegram",
    "whatsapp",
    "credentials_form",
    "unknown",
    "error",
]


class WalkResult(BaseModel):
    steps: list[WalkStep] = Field(default_factory=list)
    final_url: str = ""
    harvested_fields: list[str] = Field(default_factory=list)
    funnel_terminus: FunnelTerminus = "unknown"
    error: Optional[str] = None


# ─── Domain intel output ────────────────────────────────────────────────────


class DomainIntel(BaseModel):
    domain: str
    age_days: Optional[int] = None
    registrar: Optional[str] = None
    ssl_age_days: Optional[int] = None
    flags: list[str] = Field(default_factory=list)
    error: Optional[str] = None


# ─── Card contract written to incidents.investigation ───────────────────────


class HowWeCaughtItEntry(BaseModel):
    agent: AgentTag
    finding: str


class WhatTheySent(BaseModel):
    raw: str
    tells: list[Tell] = Field(default_factory=list)


class CardEvidence(BaseModel):
    domain: Optional[str] = None
    domain_age_days: Optional[int] = None
    final_url: Optional[str] = None
    harvested_fields: list[str] = Field(default_factory=list)
    funnel_terminus: Optional[FunnelTerminus] = None


class CardContract(BaseModel):
    scam_type: str
    what_they_sent: WhatTheySent
    what_they_wanted: str
    how_we_caught_it: list[HowWeCaughtItEntry] = Field(default_factory=list)
    how_to_spot_it: list[str] = Field(default_factory=list)
    evidence: CardEvidence = Field(default_factory=CardEvidence)
