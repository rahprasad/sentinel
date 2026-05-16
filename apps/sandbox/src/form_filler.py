"""Decoy form-fill heuristics.

Every value here is fake but well-formed: Luhn-valid card, zip in the
range, never real PII. The whole point of the sandbox is that the
scammer's funnel "succeeds" on our decoys so we observe the terminus.
"""
from __future__ import annotations

import re

# Order matters — more specific patterns first.
_DECOY_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"cvv|cvc|security[\s_-]*code"), "123"),
    (re.compile(r"card|cc|credit|ccnumber|pan"), "4242424242424242"),
    (re.compile(r"expir|expiration|exp[\s_-]*date"), "12/29"),
    (re.compile(r"ssn|social[\s_-]*security"), "000-00-0000"),
    (re.compile(r"zip|postal"), "90210"),
    (re.compile(r"phone|mobile|tel"), "5555550100"),
    (re.compile(r"address|street"), "123 Main St"),
    (re.compile(r"city"), "Beverly Hills"),
    (re.compile(r"state|province|region"), "CA"),
    (re.compile(r"country"), "US"),
    (re.compile(r"dob|birth"), "01/01/1990"),
    (re.compile(r"email|e-?mail"), "decoy@example.com"),
    (re.compile(r"first[\s_-]*name|fname|given"), "John"),
    (re.compile(r"last[\s_-]*name|lname|surname|family"), "Smith"),
    (re.compile(r"name|full"), "John Smith"),
    (re.compile(r"username|user[\s_-]*id|login"), "decoy_user"),
    (re.compile(r"password|pass|pin"), "Decoy12345!"),
    (re.compile(r"wallet|seed|mnemonic|private[\s_-]*key"), "decoy decoy decoy decoy decoy decoy"),
]

# Maps the same haystack to a normalised label the synthesizer can describe.
_CANONICAL_LABEL: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"cvv|cvc"), "cvv"),
    (re.compile(r"card|cc|credit|pan"), "card_number"),
    (re.compile(r"expir|exp[\s_-]*date"), "card_expiration"),
    (re.compile(r"ssn|social[\s_-]*security"), "ssn"),
    (re.compile(r"zip|postal"), "zip"),
    (re.compile(r"phone|mobile|tel"), "phone"),
    (re.compile(r"address|street"), "address"),
    (re.compile(r"dob|birth"), "date_of_birth"),
    (re.compile(r"email|e-?mail"), "email"),
    (re.compile(r"password|pass|pin"), "password"),
    (re.compile(r"wallet|seed|mnemonic|private[\s_-]*key"), "crypto_seed"),
    (re.compile(r"name|first|last|surname|fname|lname|full"), "name"),
]


def haystack(name: str, field_type: str = "", placeholder: str = "", label: str = "") -> str:
    return " ".join(s.lower() for s in (name, field_type, placeholder, label) if s)


def decoy_for(name: str, field_type: str = "", placeholder: str = "", label: str = "") -> str:
    h = haystack(name, field_type, placeholder, label)
    for pattern, value in _DECOY_RULES:
        if pattern.search(h):
            return value
    if field_type == "number":
        return "1"
    if field_type == "checkbox":
        return "on"
    return "test"


def canonical_label(name: str, field_type: str = "", placeholder: str = "", label: str = "") -> str | None:
    """Stable label used in WalkResult.harvested_fields and the drawer icon row."""
    h = haystack(name, field_type, placeholder, label)
    for pattern, lbl in _CANONICAL_LABEL:
        if pattern.search(h):
            return lbl
    return None
