"""Compare AgentField AI paths for the investigation synthesizer contract.

Run from the investigation container or app directory:
  python -m src.diagnostics.agentfield_ai --runs 5
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import time
from typing import Any, Awaitable, Callable

import httpx
import structlog

from src.agent import app
from src.config import settings
from src.models import CardContract

structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.INFO))
log = structlog.get_logger("diag.agentfield_ai")

SYSTEM = "Write a concise scam investigation card as JSON."
USER = """BODY:
Your USPS parcel is held. Pay a small redelivery fee at https://usps-redelivery-help.example/pay today.

TRIAGE:
{"is_scam": true, "confidence": 0.98, "scam_type": "delivery", "tells": [{"span": "Pay a small redelivery fee", "why": "Creates urgency around a fee."}], "reasoning": "Fake delivery-fee phishing."}

DOMAIN_INTEL:
{"domain": "usps-redelivery-help.example", "age_days": 2, "registrar": "Example Registrar", "flags": ["recently_registered"]}

SANDBOX_WALK:
{"steps": [], "final_url": "https://usps-redelivery-help.example/pay", "harvested_fields": ["name", "card_number"], "funnel_terminus": "payment_processor"}
"""


async def _direct_tokenrouter(timeout: float) -> dict[str, Any]:
    model = settings.synthesizer_model
    if model.startswith("openai/"):
        model = model.removeprefix("openai/")
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{settings.tokenrouter_base_url.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.tokenrouter_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": USER},
                ],
                "temperature": settings.synthesizer_temperature,
                "max_tokens": 900,
            },
        )
        response.raise_for_status()
        return response.json()


async def _timed(
    label: str,
    call: Callable[[], Awaitable[Any]],
    *,
    timeout: float,
) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        result = await asyncio.wait_for(call(), timeout=timeout)
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        parsed = result.model_dump() if hasattr(result, "model_dump") else result
        return {
            "label": label,
            "ok": True,
            "elapsed_ms": elapsed_ms,
            "result_type": type(result).__name__,
            "result_preview": json.dumps(parsed, default=str)[:500],
        }
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        return {
            "label": label,
            "ok": False,
            "elapsed_ms": elapsed_ms,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


async def _run_once(timeout: float) -> list[dict[str, Any]]:
    return [
        await _timed(
            "direct_tokenrouter_json",
            lambda: _direct_tokenrouter(timeout),
            timeout=timeout,
        ),
        await _timed(
            "agentfield_no_schema",
            lambda: app.ai(system=SYSTEM, user=USER, temperature=settings.synthesizer_temperature),
            timeout=timeout,
        ),
        await _timed(
            "agentfield_schema",
            lambda: app.ai(
                system=SYSTEM,
                user=USER,
                schema=CardContract,
                temperature=settings.synthesizer_temperature,
            ),
            timeout=timeout,
        ),
    ]


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=settings.synthesizer_timeout_seconds)
    args = parser.parse_args()

    results: list[dict[str, Any]] = []
    for run in range(1, args.runs + 1):
        for result in await _run_once(args.timeout):
            result["run"] = run
            results.append(result)
            log.info("agentfield_ai_diag_result", **result)

    summary = {
        label: {
            "passes": sum(1 for r in results if r["label"] == label and r["ok"]),
            "runs": sum(1 for r in results if r["label"] == label),
            "max_elapsed_ms": max(
                (r["elapsed_ms"] for r in results if r["label"] == label),
                default=0,
            ),
        }
        for label in {r["label"] for r in results}
    }
    print(json.dumps({"summary": summary, "results": results}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
