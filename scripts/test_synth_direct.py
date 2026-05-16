#!/usr/bin/env python3
"""Direct test of the synthesizer LLM path.

Bypasses AgentField — calls TokenRouter directly via the openai client with
the same prompt the production synthesizer uses. Validates:
  - TokenRouter API key + base URL work
  - GLM-4.6 (z-ai/glm-4.6) produces valid card JSON
  - Our prompt at apps/investigation/prompts/synthesize.md elicits the right shape

Run:
    apps/investigation/.venv/bin/python scripts/test_synth_direct.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI

REPO = Path(__file__).resolve().parents[1]
load_dotenv(REPO / ".env")

PROMPT_PATH = REPO / "apps" / "investigation" / "prompts" / "synthesize.md"

SAMPLE = {
    "body": (
        "Your USPS package could not be delivered. Pay the $1.99 redelivery "
        "fee within 24 hours at https://usps-redelivery.co/track to reschedule."
    ),
    "triage": {
        "is_scam": True,
        "confidence": 0.96,
        "scam_type": "fake-support",
        "tells": [
            {"span": "usps-redelivery.co", "why": "Domain does not match usps.com."},
            {"span": "$1.99 redelivery fee", "why": "USPS does not charge redelivery fees."},
            {"span": "within 24 hours", "why": "Urgency is a phishing lever."},
        ],
        "reasoning": "Look-alike USPS domain plus a small fee plus urgency.",
    },
    "domain_intel": {
        "domain": "usps-redelivery.co",
        "age_days": 5,
        "registrar": "Namecheap",
        "ssl_age_days": 4,
        "flags": ["recently_registered", "young_ssl", "no_business_email"],
    },
    "sandbox_walk": {
        "steps": [
            {
                "screenshot_url": "https://placehold.co/800/0/0/png?text=step1",
                "url": "https://usps-redelivery.co/track",
                "form_fields": ["tracking_number"],
                "page_text": "Track your package",
            },
            {
                "screenshot_url": "https://placehold.co/800/0/0/png?text=step2",
                "url": "https://usps-redelivery.co/pay",
                "form_fields": ["card_number", "cvv", "ssn"],
                "page_text": "Pay your redelivery fee. Confirm SSN for identity.",
            },
        ],
        "final_url": "https://usps-redelivery.co/pay",
        "harvested_fields": ["card_number", "cvv", "ssn"],
        "funnel_terminus": "credentials_form",
    },
}


def build_user_message() -> str:
    return (
        f"BODY:\n{SAMPLE['body']}\n\n"
        f"TRIAGE:\n{json.dumps(SAMPLE['triage'], indent=2)}\n\n"
        f"DOMAIN_INTEL:\n{json.dumps(SAMPLE['domain_intel'], indent=2)}\n\n"
        f"SANDBOX_WALK:\n{json.dumps(SAMPLE['sandbox_walk'], indent=2)}"
    )


async def main() -> int:
    key = os.environ.get("TOKENROUTER_API_KEY") or ""
    base = os.environ.get("TOKENROUTER_BASE_URL") or ""
    if not key or not base:
        print("TOKENROUTER_API_KEY / TOKENROUTER_BASE_URL not set in .env", file=sys.stderr)
        return 2

    # The id without the litellm `openai/` prefix — we're calling the endpoint
    # directly, not via LiteLLM. This is what TokenRouter expects.
    model = os.environ.get("SYNTHESIZER_MODEL", "openai/z-ai/glm-4.6").removeprefix("openai/")
    print(f"-> model:   {model}")
    print(f"-> base:    {base}")
    print(f"-> prompt:  {PROMPT_PATH}")

    client = AsyncOpenAI(api_key=key, base_url=base)
    system = PROMPT_PATH.read_text()
    user = build_user_message()

    resp = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    content = resp.choices[0].message.content or ""
    try:
        card = json.loads(content)
    except json.JSONDecodeError as exc:
        print(f"FAIL: model returned non-JSON: {exc}", file=sys.stderr)
        print(content[:500])
        return 3

    required = ("scam_type", "what_they_sent", "what_they_wanted", "how_we_caught_it", "how_to_spot_it")
    missing = [k for k in required if k not in card]
    if missing:
        print(f"FAIL: missing fields: {missing}", file=sys.stderr)
        return 4

    print("\n=== CARD ===")
    print(json.dumps(card, indent=2)[:2400])
    print("\nOK")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
