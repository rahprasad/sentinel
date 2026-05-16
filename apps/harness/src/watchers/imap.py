"""IMAP IDLE watcher — real-time email monitoring.

Connects to an IMAP server using aioimaplib, enters IDLE mode, and
processes incoming messages as they arrive.  Reconnects with
exponential backoff on disconnect.
"""

from __future__ import annotations

import asyncio
import email as email_lib
import email.policy
import re
from email.header import decode_header
from typing import Optional
from urllib.parse import urlparse

import aioimaplib
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config import settings
from src.db.pool import get_pool
from src.normalize.envelope import normalize_envelope

logger = structlog.get_logger()

# Backoff state for reconnect
_BACKOFF_BASE = 2
_BACKOFF_CAP = 120  # 2 min max between retries


def _decode_header_value(raw: str) -> str:
    """Decode RFC-2047 encoded header value."""
    parts = decode_header(raw or "")
    decoded: list[str] = []
    for data, charset in parts:
        if isinstance(data, bytes):
            decoded.append(data.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(data)
    return " ".join(decoded)


def _extract_sender(from_header: str) -> str:
    """Extract a clean sender string from the From header."""
    return _decode_header_value(from_header)


def _extract_domain(address: str) -> str:
    """Extract the domain from an email address like 'foo@example.com'."""
    if "<" in address and ">" in address:
        addr = address[address.index("<") + 1 : address.index(">")]
    elif "@" in address:
        addr = address
    else:
        return ""
    try:
        return addr.split("@")[1].strip().lower()
    except (IndexError, AttributeError):
        return ""


def _get_text_body(msg: email_lib.message.Message) -> str:
    """Extract the best text body from an email message."""
    if msg.is_multipart():
        # Prefer text/plain
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")

        # Fallback to text/html stripped of tags
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    html = payload.decode(charset, errors="replace")
                    return re.sub(r"<[^>]+>", " ", html)

    # Not multipart — just return the payload
    payload = msg.get_payload(decode=True)
    if payload:
        charset = msg.get_content_charset() or "utf-8"
        return payload.decode(charset, errors="replace")
    return ""


async def _fetch_and_process(
    client: aioimaplib.IMAP4_SSL, uid: str
) -> Optional[dict]:
    """Fetch a single message by UID and return a normalized envelope dict."""
    _, response = await client.uid("fetch", uid, "(RFC822)")
    # aioimaplib returns lines; find the RFC822 payload
    raw_email: Optional[bytes] = None
    for i, line in enumerate(response):
        if isinstance(line, bytes) and b"RFC822" not in line:
            raw_email = line
            break
        if isinstance(line, str) and "RFC822" in line:
            # The next item might be the bytes body
            if i + 1 < len(response) and isinstance(response[i + 1], bytes):
                raw_email = response[i + 1]
                break

    if raw_email is None:
        logger.warning("imap.fetch_failed", uid=uid)
        return None

    msg = email_lib.message_from_bytes(raw_email, policy=email.policy.default)
    sender = _extract_sender(msg.get("From", ""))
    subject = _decode_header_value(msg.get("Subject", ""))
    body = _get_text_body(msg)

    envelope = normalize_envelope({
        "source": "email_imap",
        "sender": sender,
        "subject": subject,
        "body": body,
    })
    return envelope


async def _insert_incident(envelope: dict) -> None:
    """Insert a normalized envelope into the incidents table."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO incidents (source, sender, subject, body, iocs, status)
            VALUES ($1, $2, $3, $4, $5, 'triaging')
            """,
            envelope["source"],
            envelope["sender"],
            envelope["subject"],
            envelope["body"],
            # asyncpg handles dict -> jsonb automatically
            envelope["iocs"],
        )
        # Bump scanned counter for email_imap
        await conn.execute(
            """
            INSERT INTO harness_status (source, last_check, state, items_scanned_total)
            VALUES ('email_imap', now(), 'active', 1)
            ON CONFLICT (source) DO UPDATE
              SET last_check = now(),
                  items_scanned_total = harness_status.items_scanned_total + 1,
                  state = 'active'
            """
        )
    logger.info(
        "imap.incident_inserted",
        sender=envelope["sender"][:40],
        subject=envelope["subject"][:60],
    )


@retry(
    retry=retry_if_exception_type(Exception),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=4, max=120),
)
async def _connect_imap() -> aioimaplib.IMAP4_SSL:
    """Connect and authenticate to the IMAP server. Retries on failure."""
    client = aioimaplib.IMAP4_SSL(
        host=settings.IMAP_HOST,
        port=settings.IMAP_PORT,
    )
    await client.wait_hello_from_server()
    await client.login(settings.IMAP_USERNAME, settings.IMAP_PASSWORD)
    await client.select(settings.IMAP_MAILBOX)
    logger.info("imap.connected", host=settings.IMAP_HOST)
    return client


async def imap_watcher() -> None:
    """Persistent IMAP IDLE watcher coroutine.

    Connects, enters IDLE, processes new messages, and reconnects with
    exponential backoff on any disconnect or error.
    """
    if not settings.IMAP_USERNAME or not settings.IMAP_PASSWORD:
        logger.warning("imap.no_credentials — skipping IMAP watcher")
        return

    backoff = _BACKOFF_BASE

    while True:
        client: Optional[aioimaplib.IMAP4_SSL] = None
        try:
            client = await _connect_imap()

            # Reset backoff on successful connect
            backoff = _BACKOFF_BASE

            while True:
                # Enter IDLE and wait for EXISTS (new message)
                idle_result = await client.idle_start(timeout=300)
                # idle_start returns; we check for new messages
                # by examining the responses
                responses = client.get_server_responses()
                exists_found = any(
                    b"EXISTS" in r if isinstance(r, bytes) else "EXISTS" in r
                    for r in responses
                )

                if exists_found:
                    # Fetch all UNSEEN messages
                    _, data = await client.uid("search", "UNSEEN")
                    if data and data[0]:
                        uids = data[0].split()
                        for uid in uids:
                            uid_str = uid.decode() if isinstance(uid, bytes) else uid
                            envelope = await _fetch_and_process(client, uid_str)
                            if envelope:
                                await _insert_incident(envelope)

                # Done with IDLE
                await client.idle_done()

        except asyncio.CancelledError:
            logger.info("imap.cancelled")
            if client:
                try:
                    await client.logout()
                except Exception:
                    pass
            return

        except Exception as exc:
            logger.error(
                "imap.error",
                error=str(exc),
                retry_in=backoff,
            )
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, _BACKOFF_CAP)
