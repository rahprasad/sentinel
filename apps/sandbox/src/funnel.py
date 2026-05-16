"""Funnel terminus detection.

We classify what the scam funnel was actually trying to do. The judges'
"what did they want" answer comes from here.
"""
from __future__ import annotations

from urllib.parse import urlparse

from .models import FunnelTerminus

_PAYMENT_DOMAINS: tuple[str, ...] = (
    "stripe.com",
    "checkout.stripe.com",
    "js.stripe.com",
    "paypal.com",
    "paypalobjects.com",
    "braintreepayments.com",
    "squareup.com",
    "checkout.square.site",
    "cashapp.com",
    "venmo.com",
    "zellepay.com",
    "wise.com",
    "moonpay.com",
    "ramp.network",
    "coinbase.com",
    "binance.com",
    "kraken.com",
)

_TELEGRAM_DOMAINS: tuple[str, ...] = (
    "t.me",
    "telegram.me",
    "telegram.org",
    "telegram.dog",
)

_WHATSAPP_DOMAINS: tuple[str, ...] = (
    "wa.me",
    "whatsapp.com",
    "chat.whatsapp.com",
    "api.whatsapp.com",
)

_HIGH_RISK_FIELDS: frozenset[str] = frozenset(
    {"card_number", "cvv", "ssn", "crypto_seed", "password"}
)


def _domain_of(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def _matches(domain: str, candidates: tuple[str, ...]) -> bool:
    return any(domain == d or domain.endswith("." + d) for d in candidates)


def detect(url: str, harvested_fields: set[str]) -> FunnelTerminus:
    """Order: explicit hand-off > credentials form > unknown."""
    domain = _domain_of(url)
    if _matches(domain, _TELEGRAM_DOMAINS):
        return "telegram"
    if _matches(domain, _WHATSAPP_DOMAINS):
        return "whatsapp"
    if _matches(domain, _PAYMENT_DOMAINS):
        return "payment_processor"
    if harvested_fields & _HIGH_RISK_FIELDS:
        return "credentials_form"
    return "unknown"


def is_terminal_domain(url: str) -> bool:
    """True if we should stop walking after this navigation regardless of step budget."""
    domain = _domain_of(url)
    return (
        _matches(domain, _PAYMENT_DOMAINS)
        or _matches(domain, _TELEGRAM_DOMAINS)
        or _matches(domain, _WHATSAPP_DOMAINS)
    )
