"""Synthesizer reasoner.

Combines triage + domain-intel + walker evidence into the user-facing card.
The LLM call goes through `app.ai(schema=CardContract)` — AgentField uses
LiteLLM so the model string is in `provider/model` form and TokenRouter is
addressed via the standard OPENAI_API_BASE / OPENAI_API_KEY env vars.

Estimated loss is computed deterministically (not asked of the LLM) so the
headline "saved you $X" can never hallucinate.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import structlog

from .agent import app
from .config import settings
from .models import (
    CardContract,
    CardEvidence,
    DomainIntel,
    HowWeCaughtItEntry,
    TriageResult,
    WalkResult,
    WhatTheySent,
)

log = structlog.get_logger("synthesizer")

_PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "synthesize.md"

_BASE_LOSS_BY_TYPE: dict[str, int] = {
    "delivery": 50,
    "refund": 300,
    "phishing": 400,
    "support": 800,
    "fake-support": 800,
    "crypto": 2000,
    "crypto-airdrop": 2000,
    "pig-butchering": 4000,
    "romance": 5000,
}

_IOC_HANDLE_RE = re.compile(r"@([A-Za-z0-9_]{3,32})")
_IOC_WALLET_ETH_RE = re.compile(r"0x[a-fA-F0-9]{40}")
_IOC_WALLET_BTC_RE = re.compile(r"\bbc1[a-z0-9]{6,80}\b|\b[13][a-km-zA-HJ-NP-Z1-9]{25,34}\b")


@app.reasoner(tags=["sentinel", "synthesizer"])
async def synthesize(
    incident_id: str,
    body: str,
    triage: TriageResult,
    domain_intel: Optional[DomainIntel],
    walker: Optional[WalkResult],
) -> CardContract:
    """Produce the user-facing card. Caller computes loss + IOCs separately."""
    system = _PROMPT_PATH.read_text()
    user = _build_user_message(body, triage, domain_intel, walker)

    try:
        raw = await app.ai(
            system=system,
            user=user,
            schema=CardContract,
            temperature=settings.synthesizer_temperature,
        )
    except Exception as exc:
        log.warning("synth_llm_failed", incident_id=incident_id, error=str(exc))
        return _fallback_card(body=body, triage=triage, domain_intel=domain_intel, walker=walker)

    return _repair_card(raw, body=body, domain_intel=domain_intel, walker=walker)


# ─── Prompt assembly ─────────────────────────────────────────────────────────


def _build_user_message(
    body: str,
    triage: TriageResult,
    domain_intel: Optional[DomainIntel],
    walker: Optional[WalkResult],
) -> str:
    triage_json = json.dumps(triage.model_dump(), ensure_ascii=False, indent=2)
    di_json = (
        json.dumps(domain_intel.model_dump(), ensure_ascii=False, indent=2)
        if domain_intel is not None
        else '"skipped — no URL"'
    )
    walker_json = (
        json.dumps(walker.model_dump(), ensure_ascii=False, indent=2)
        if walker is not None
        else '"skipped — no URL in message"'
    )
    return (
        f"BODY:\n{body}\n\n"
        f"TRIAGE:\n{triage_json}\n\n"
        f"DOMAIN_INTEL:\n{di_json}\n\n"
        f"SANDBOX_WALK:\n{walker_json}"
    )


# ─── Repair / fallback ──────────────────────────────────────────────────────


def _repair_card(
    card: CardContract,
    *,
    body: str,
    domain_intel: Optional[DomainIntel],
    walker: Optional[WalkResult],
) -> CardContract:
    """Anchor LLM output to the evidence we already have."""
    repaired = card.model_copy(deep=True)
    repaired.what_they_sent.raw = body

    ev = repaired.evidence
    if walker is not None:
        if not ev.final_url and walker.final_url:
            ev.final_url = walker.final_url
        if not ev.harvested_fields:
            ev.harvested_fields = list(walker.harvested_fields)
        if not ev.funnel_terminus:
            ev.funnel_terminus = walker.funnel_terminus
    if domain_intel is not None:
        if not ev.domain and domain_intel.domain:
            ev.domain = domain_intel.domain
        if ev.domain_age_days is None and domain_intel.age_days is not None:
            ev.domain_age_days = domain_intel.age_days
    return repaired


def _fallback_card(
    *,
    body: str,
    triage: TriageResult,
    domain_intel: Optional[DomainIntel],
    walker: Optional[WalkResult],
) -> CardContract:
    """When the LLM is unavailable, ship a deterministic card so the demo never blanks."""
    how: list[HowWeCaughtItEntry] = [
        HowWeCaughtItEntry(agent="triage", finding=triage.reasoning or "Triage flagged this message."),
    ]
    if domain_intel and domain_intel.age_days is not None:
        how.append(
            HowWeCaughtItEntry(
                agent="domain-intel",
                finding=f"Domain registered {domain_intel.age_days} days ago"
                + (f" via {domain_intel.registrar}." if domain_intel.registrar else "."),
            )
        )
    if walker and walker.harvested_fields:
        how.append(
            HowWeCaughtItEntry(
                agent="sandbox-walker",
                finding="Funnel asked for: " + ", ".join(walker.harvested_fields[:4]) + ".",
            )
        )

    return CardContract(
        scam_type=triage.scam_type or "Suspicious message",
        what_they_sent=WhatTheySent(raw=body, tells=list(triage.tells)),
        what_they_wanted=(
            "They wanted " + ", ".join(walker.harvested_fields[:3]) + "."
            if walker and walker.harvested_fields
            else "They wanted to phish you."
        ),
        how_we_caught_it=how,
        how_to_spot_it=[
            "Slow down on anything that creates urgency.",
            "Verify by going to the brand's website directly, never by clicking the link.",
        ],
        evidence=CardEvidence(
            domain=(domain_intel.domain if domain_intel else None),
            domain_age_days=(domain_intel.age_days if domain_intel else None),
            final_url=(walker.final_url if walker else None),
            harvested_fields=(walker.harvested_fields if walker else []),
            funnel_terminus=(walker.funnel_terminus if walker else None),
        ),
    )


# ─── Deterministic computations ─────────────────────────────────────────────


def estimated_loss_usd(scam_type: str, walker: Optional[WalkResult]) -> int:
    base = _lookup_base_loss(scam_type)
    multiplier = 1
    if walker:
        high = {"card_number", "ssn"}
        if walker.funnel_terminus == "credentials_form" and high.issubset(set(walker.harvested_fields)):
            multiplier = 2
        elif walker.funnel_terminus == "payment_processor":
            multiplier = 2
    return base * multiplier


def _lookup_base_loss(scam_type: str) -> int:
    key = scam_type.lower()
    for label, value in _BASE_LOSS_BY_TYPE.items():
        if label in key:
            return value
    return 250


def extract_iocs(
    scam_type: str,
    body: str,
    walker: Optional[WalkResult],
    domain_intel: Optional[DomainIntel],
) -> list[tuple[str, str, Optional[str]]]:
    iocs: list[tuple[str, str, Optional[str]]] = []
    seen: set[tuple[str, str]] = set()

    def add(value: str, ioc_type: str) -> None:
        v = value.strip()
        if not v:
            return
        key = (v.lower(), ioc_type)
        if key in seen:
            return
        seen.add(key)
        iocs.append((v, ioc_type, scam_type or None))

    if domain_intel and domain_intel.domain:
        add(domain_intel.domain, "domain")

    if walker:
        for step in walker.steps:
            host = urlparse(step.url).hostname
            if host:
                add(host, "domain")
        if walker.final_url:
            host = urlparse(walker.final_url).hostname
            if host:
                add(host, "domain")
            add(walker.final_url, "url")

    for match in _IOC_HANDLE_RE.findall(body or ""):
        add("@" + match, "handle")
    for match in _IOC_WALLET_ETH_RE.findall(body or ""):
        add(match, "wallet")
    for match in _IOC_WALLET_BTC_RE.findall(body or ""):
        if not match.startswith("0x"):
            add(match, "wallet")

    return iocs
