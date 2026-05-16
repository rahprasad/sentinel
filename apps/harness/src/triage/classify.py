"""LLM-based triage classification via TokenRouter.

Calls a cheap/fast model (qwen-flash or glm-flash) to classify messages
as scam or safe, extract tells, and determine scam type.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import httpx
import structlog

from src.agent import app
from src.config import settings
from src.ioc.brands import check_brand_mismatch
from src.triage.models import TriageResult

logger = structlog.get_logger()

# Load the triage prompt template
_PROMPT_PATH = Path(__file__).resolve().parent.parent.parent / "prompts" / "triage.md"


def _load_prompt_template() -> str:
    """Load the triage prompt template from disk."""
    if _PROMPT_PATH.exists():
        return _PROMPT_PATH.read_text(encoding="utf-8")
    # Fallback inline template if file doesn't exist yet
    return (
        "You are a scam triage classifier. Output JSON only:\n"
        '{\n'
        '  "is_scam": bool,\n'
        '  "confidence": 0.0-1.0,\n'
        '  "scam_type": "phishing"|"romance"|"delivery"|"refund"|"crypto"|"support"|"other"|"none",\n'
        '  "tells": [{"span": "exact text from message", "why": "one sentence"}],\n'
        '  "reasoning": "one sentence"\n'
        '}\n'
        "\n"
        "Rules:\n"
        '- "tells" highlight 2-4 specific spans a human could learn to spot.\n'
        "- If under 0.6 confidence, set is_scam=false.\n"
        "\n"
        "Message:\n"
        "From: {sender}\n"
        "Subject: {subject}\n"
        "Body: {body}\n"
        "URLs: {urls}\n"
    )


async def classify_with_llm(
    sender: str,
    subject: str,
    body: str,
    urls: list[str],
    iocs: dict,
) -> dict:
    """Classify a message using the LLM via TokenRouter.

    Returns a triage result dict:
      {is_scam, confidence, scam_type, tells, reasoning}
    """
    # Pre-LLM check: brand-domain mismatch heuristic
    brand_tells = check_brand_mismatch(body, urls, sender)

    # Build the user message
    template = _load_prompt_template()
    user_message = (
        template
        .replace("{sender}", sender)
        .replace("{subject}", subject)
        .replace("{body}", body[:2000])  # Truncate very long bodies
        .replace("{urls}", ", ".join(urls) if urls else "none")
    )

    # If we have brand mismatch tells, append them as context
    if brand_tells:
        extra_context = "\n\nAdditional heuristic findings:\n"
        for tell in brand_tells:
            extra_context += f"- Domain mismatch: {tell['span']} — {tell['why']}\n"
        user_message += extra_context

    # Call TokenRouter through AgentField; fall back to direct HTTP if the
    # control-plane/SDK path is unavailable during local demos.
    result = await _call_agentfield(user_message)

    # Merge brand tells into the result tells if not already present
    if brand_tells and result.get("is_scam"):
        existing_spans = {t.get("span") for t in result.get("tells", [])}
        for tell in brand_tells:
            if tell["span"] not in existing_spans:
                result.setdefault("tells", []).append(tell)

    # Apply confidence threshold
    threshold = settings.TRIAGE_CONFIDENCE_THRESHOLD
    if result.get("confidence", 0) < threshold:
        result["is_scam"] = False
        if result.get("scam_type") not in ("none", None):
            result["scam_type"] = "none"

    return result


async def _call_agentfield(user_message: str) -> dict:
    """Classify via AgentField structured AI, with direct TokenRouter fallback.

    Returns parsed JSON from the model response.
    Falls back to a safe default on any error.
    """
    if not settings.TOKENROUTER_API_KEY:
        logger.warning("triage.no_api_key — returning safe default")
        return _safe_default("No API key configured")

    if not settings.TRIAGE_AGENTFIELD_AI_ENABLED:
        return await _call_tokenrouter_direct(user_message)

    started = time.perf_counter()
    timeout = settings.TRIAGE_AGENTFIELD_TIMEOUT_SECONDS
    logger.info(
        "triage.agentfield_start",
        model=settings.TRIAGE_MODEL,
        timeout_seconds=timeout,
        schema="TriageResult",
    )
    try:
        result = await asyncio.wait_for(
            app.ai(
                system="You are a scam triage classifier. Output JSON only.",
                user=user_message,
                schema=TriageResult,
                temperature=0.1,
            ),
            timeout=timeout,
        )
        logger.info(
            "triage.agentfield_classified",
            is_scam=result.is_scam,
            confidence=result.confidence,
            elapsed_ms=round((time.perf_counter() - started) * 1000),
        )
        return result.model_dump()
    except asyncio.TimeoutError:
        logger.warning(
            "triage.agentfield_timeout",
            timeout_seconds=timeout,
            elapsed_ms=round((time.perf_counter() - started) * 1000),
            fallback="tokenrouter_direct",
        )
        return await _call_tokenrouter_direct(user_message)
    except Exception as exc:
        logger.warning(
            "triage.agentfield_error",
            error=str(exc),
            elapsed_ms=round((time.perf_counter() - started) * 1000),
            fallback="tokenrouter_direct",
        )
        return await _call_tokenrouter_direct(user_message)


async def _call_tokenrouter_direct(user_message: str) -> dict:
    """Fallback direct OpenAI-compatible TokenRouter call."""

    url = f"{settings.TOKENROUTER_BASE_URL.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.TOKENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    model = settings.TRIAGE_MODEL
    if model.startswith("openai/"):
        model = model.removeprefix("openai/")

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a scam triage classifier. Output JSON only."},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.1,
        "max_tokens": 512,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        # Extract the content from the response
        content = data["choices"][0]["message"]["content"]

        # Parse JSON from the model output
        # Model might wrap in markdown code blocks
        content = content.strip()
        if content.startswith("```"):
            # Strip markdown code fences
            lines = content.split("\n")
            lines = [l for l in lines if not l.startswith("```")]
            content = "\n".join(lines)

        result = json.loads(content)
        logger.info(
            "triage.direct_llm_classified",
            is_scam=result.get("is_scam"),
            confidence=result.get("confidence"),
        )
        return result

    except (httpx.HTTPError, json.JSONDecodeError, KeyError, IndexError) as exc:
        logger.error("triage.llm_error", error=str(exc))
        return _safe_default(f"LLM error: {exc}")


def _safe_default(reason: str) -> dict:
    """Return a safe default triage result (not a scam, low confidence)."""
    return {
        "is_scam": False,
        "confidence": 0.0,
        "scam_type": "none",
        "tells": [],
        "reasoning": reason,
    }
