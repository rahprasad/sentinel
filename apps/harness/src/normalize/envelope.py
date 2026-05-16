"""Normalize incoming messages into a uniform envelope.

Regardless of source (IMAP, webhook, screenshot), the harness pipeline
works with a single envelope shape:
  {source, sender, subject, body, iocs: {urls, phones, wallets, handles}}
"""

from __future__ import annotations

from src.ioc.extract import extract_iocs


def normalize_envelope(raw: dict) -> dict:
    """Normalize a raw message dict into the harness envelope format.

    Args:
        raw: dict with at least `source`, `sender`, `subject`, `body`.
             May contain pre-extracted IOCs.

    Returns:
        Uniform envelope dict with IOCs populated.
    """
    source = raw.get("source", "email_webhook")
    sender = (raw.get("sender") or "").strip()
    subject = (raw.get("subject") or "").strip()
    body = (raw.get("body") or "").strip()

    # Combine all text for IOC extraction
    full_text = f"{subject}\n{body}"

    # If IOCs were pre-extracted (e.g. from screenshot VLM), merge them
    pre_iocs = raw.get("iocs", {})
    extracted_iocs = extract_iocs(full_text)

    # Merge: extracted wins for overlapping keys
    merged_iocs = {
        "urls": list(dict.fromkeys(pre_iocs.get("urls", []) + extracted_iocs.get("urls", []))),
        "phones": list(dict.fromkeys(pre_iocs.get("phones", []) + extracted_iocs.get("phones", []))),
        "wallets": list(dict.fromkeys(pre_iocs.get("wallets", []) + extracted_iocs.get("wallets", []))),
        "handles": list(dict.fromkeys(pre_iocs.get("handles", []) + extracted_iocs.get("handles", []))),
    }

    return {
        "source": source,
        "sender": sender,
        "subject": subject,
        "body": body,
        "iocs": merged_iocs,
    }
