"""Compare direct TokenRouter and AgentField AI paths for triage.

Run from the harness container or app directory:
  python -m src.diagnostics.agentfield_ai --runs 5
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import time
from typing import Any, Awaitable, Callable

import structlog

from src.agent import app
from src.config import settings
from src.triage.classify import _call_tokenrouter_direct
from src.triage.models import TriageResult

structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.INFO))
log = structlog.get_logger("diag.agentfield_ai")

SYSTEM = "You are a scam triage classifier. Output JSON only."
USER = """Classify this message.
From: USPS Delivery <notice@usps-redelivery-help.example>
Subject: Package delivery failed
Body: Your parcel is held. Pay a $0.30 redelivery fee now at https://usps-redelivery-help.example/pay or it will be returned today.
URLs: https://usps-redelivery-help.example/pay
"""


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
            lambda: _call_tokenrouter_direct(USER),
            timeout=timeout,
        ),
        await _timed(
            "agentfield_no_schema",
            lambda: app.ai(system=SYSTEM, user=USER, temperature=0.1),
            timeout=timeout,
        ),
        await _timed(
            "agentfield_schema",
            lambda: app.ai(system=SYSTEM, user=USER, schema=TriageResult, temperature=0.1),
            timeout=timeout,
        ),
    ]


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=settings.TRIAGE_AGENTFIELD_TIMEOUT_SECONDS)
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
