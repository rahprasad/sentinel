"""Domain intel skill.

Deterministic — no LLM call — so registered as `@app.skill()`. Uses
python-whois for registration data and Python's stdlib ssl for cert age.
Both run in a thread pool. Failures degrade gracefully via `flags`.

(Bright Data has no single WHOIS endpoint; their API key is used to power
the sandbox walker's residential proxy instead — see apps/sandbox/.)
"""
from __future__ import annotations

import asyncio
import socket
import ssl
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urlparse

import structlog

from .agent import app
from .models import DomainIntel

log = structlog.get_logger("domain_intel")

_RECENTLY_REGISTERED_DAYS = 30
_YOUNG_SSL_DAYS = 30

_PERSONAL_EMAIL_HOSTS = (
    "gmail.com",
    "yahoo.com",
    "hotmail.com",
    "outlook.com",
    "proton.me",
    "protonmail.com",
    "icloud.com",
    "aol.com",
    "yandex.com",
    "mail.com",
)
_PRIVACY_PROXY_HINTS = (
    "whoisguard",
    "privacy",
    "privacyprotect",
    "domainsbyproxy",
    "withheld",
    "redacted",
)


@app.skill(tags=["sentinel", "domain-intel"])
async def investigate_domain(url: str) -> DomainIntel:
    """Look up registration metadata + SSL cert age for a URL's domain."""
    domain = _domain_of(url)
    if not domain:
        return DomainIntel(domain="", error="no domain in url")

    whois_data, ssl_not_before = await asyncio.gather(
        _whois(domain),
        _ssl_not_before(domain),
        return_exceptions=False,
    )

    now = datetime.now(timezone.utc)
    age_days = _days_since(whois_data.get("creation_date"), now)
    ssl_age_days = _days_since(ssl_not_before, now)
    registrar = _coerce_str(whois_data.get("registrar"))
    registrant_email = _coerce_str(whois_data.get("registrant_email"))

    flags: list[str] = []
    if age_days is not None and age_days < _RECENTLY_REGISTERED_DAYS:
        flags.append("recently_registered")
    if ssl_age_days is not None and ssl_age_days < _YOUNG_SSL_DAYS:
        flags.append("young_ssl")
    if _looks_non_business(registrant_email):
        flags.append("no_business_email")
    if whois_data.get("_error"):
        flags.append("whois_unavailable")

    return DomainIntel(
        domain=domain,
        age_days=age_days,
        registrar=registrar,
        ssl_age_days=ssl_age_days,
        flags=flags,
    )


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _domain_of(url: str) -> str:
    parsed = urlparse(url if "://" in url else f"http://{url}")
    return (parsed.hostname or "").lower()


async def _whois(domain: str) -> dict[str, Any]:
    def _lookup() -> dict[str, Any]:
        try:
            import whois  # python-whois

            data = whois.whois(domain)
            return {
                "creation_date": data.creation_date,
                "registrar": data.registrar,
                "registrant_email": getattr(data, "emails", None)
                or getattr(data, "email", None),
            }
        except Exception as exc:
            return {"_error": str(exc)}

    return await asyncio.get_event_loop().run_in_executor(None, _lookup)


async def _ssl_not_before(domain: str) -> Optional[datetime]:
    def _fetch() -> Optional[datetime]:
        try:
            ctx = ssl.create_default_context()
            with socket.create_connection((domain, 443), timeout=4) as sock:
                with ctx.wrap_socket(sock, server_hostname=domain) as ssock:
                    cert = ssock.getpeercert()
                    not_before = cert.get("notBefore") if cert else None
                    if not not_before:
                        return None
                    return datetime.strptime(
                        not_before, "%b %d %H:%M:%S %Y %Z"
                    ).replace(tzinfo=timezone.utc)
        except Exception:
            return None

    return await asyncio.get_event_loop().run_in_executor(None, _fetch)


def _days_since(value: Any, now: datetime) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        value = value[0] if value else None
    if isinstance(value, str):
        for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(value, fmt)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                value = parsed
                break
            except ValueError:
                continue
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    delta = now - value
    return max(int(delta.total_seconds() // 86400), 0)


def _coerce_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        value = value[0] if value else None
    if not value:
        return None
    return str(value)


def _looks_non_business(email: Optional[str]) -> bool:
    if not email:
        return True
    lowered = email.lower()
    if any(hint in lowered for hint in _PRIVACY_PROXY_HINTS):
        return True
    return any(host in lowered for host in _PERSONAL_EMAIL_HOSTS)
