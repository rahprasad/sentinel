"""IOC (Indicator of Compromise) extraction via regex.

Extracts URLs, phone numbers, cryptocurrency wallets, and social handles
from raw text.
"""

from __future__ import annotations

import re

# --- Regex patterns ---
URL_RE = re.compile(r"https?://[^\s<>\"]+")
PHONE_RE = re.compile(r"\+?\d[\d\-]{8,}\d")
ETH_WALLET_RE = re.compile(r"0x[a-fA-F0-9]{40}")
BTC_WALLET_RE = re.compile(r"bc1[a-z0-9]{25,}")
HANDLE_RE = re.compile(r"(?:^|[\s:])@([a-z0-9_]{3,})")


def extract_iocs(text: str) -> dict:
    """Extract IOCs from text.

    Returns:
        dict with keys: urls, phones, wallets, handles
    """
    urls = URL_RE.findall(text)
    phones = PHONE_RE.findall(text)
    eth_wallets = ETH_WALLET_RE.findall(text)
    btc_wallets = BTC_WALLET_RE.findall(text)
    wallets = list(dict.fromkeys(eth_wallets + btc_wallets))
    handles = ["@" + h for h in HANDLE_RE.findall(text)]

    return {
        "urls": urls,
        "phones": phones,
        "wallets": wallets,
        "handles": handles,
    }
