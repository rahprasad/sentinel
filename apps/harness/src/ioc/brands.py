"""Brand-domain mismatch heuristic.

Hardcoded top-20 brands mapped to their real domains.  If a message
mentions a brand but links/sends from a different domain, flag it.
"""

from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urlparse

# Top 20 brands most commonly impersonated in scams
BRAND_DOMAINS: dict[str, str] = {
    "usps": "usps.com",
    "fedex": "fedex.com",
    "ups": "ups.com",
    "dhl": "dhl.com",
    "amazon": "amazon.com",
    "apple": "apple.com",
    "microsoft": "microsoft.com",
    "netflix": "netflix.com",
    "paypal": "paypal.com",
    "chase": "chase.com",
    "wellsfargo": "wellsfargo.com",
    "bankofamerica": "bankofamerica.com",
    "citi": "citibank.com",
    "coinbase": "coinbase.com",
    "binance": "binance.com",
    "google": "google.com",
    "facebook": "facebook.com",
    "instagram": "instagram.com",
    "twitter": "twitter.com",
    "venmo": "venmo.com",
}

# Build a regex that matches any brand keyword (case-insensitive)
_BRAND_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(b) for b in BRAND_DOMAINS) + r")\b",
    re.IGNORECASE,
)


def _domain_from_url(url: str) -> str:
    """Extract the registered domain from a URL."""
    try:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        # Take last two parts (e.g. "usps-redelivery.co" → keep as-is,
        # we just compare against known domain)
        return host.lower()
    except Exception:
        return ""


def _domain_from_email(address: str) -> str:
    """Extract domain from an email address."""
    if "@" in address:
        return address.rsplit("@", 1)[-1].strip().lower()
    return ""


def check_brand_mismatch(
    body: str,
    urls: list[str],
    sender: str = "",
) -> list[dict]:
    """Check if any mentioned brand has a domain mismatch.

    Returns a list of tells: [{"span": ..., "why": ...}, ...]
    """
    tells: list[dict] = []

    # Find brands mentioned in the body
    mentioned_brands = set(m.group(1).lower() for m in _BRAND_PATTERN.finditer(body))
    if not mentioned_brands:
        return tells

    # Collect all domains present in the message
    link_domains = {_domain_from_url(u) for u in urls}
    sender_domain = _domain_from_email(sender)
    if sender_domain:
        link_domains.add(sender_domain)

    for brand in mentioned_brands:
        real_domain = BRAND_DOMAINS.get(brand)
        if not real_domain:
            continue

        # Check if any domain in the message matches the real domain
        domain_match = any(
            real_domain == d or d.endswith("." + real_domain)
            for d in link_domains
        )

        if not domain_match and link_domains:
            # Brand mentioned but no link/sender matches the real domain
            suspicious_domains = [
                d for d in link_domains
                if d and d != real_domain and not d.endswith("." + real_domain)
            ]
            if suspicious_domains:
                tells.append({
                    "span": suspicious_domains[0],
                    "why": f"Domain does not match {real_domain}",
                })

    return tells
