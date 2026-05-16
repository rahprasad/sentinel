"""IMAP IDLE watcher — real-time email monitoring.

Connects to an IMAP server using aioimaplib, enters IDLE mode, and
processes incoming messages as they arrive.  Reconnects with
exponential backoff on disconnect.
"""

from __future__ import annotations

import asyncio
import email as email_lib
import email.policy
import json
import re
from datetime import UTC, datetime, timedelta
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
_last_seen_uid: int | None = None
_last_exists_count: int | None = None


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


def _response_lines(response: object) -> list[object]:
    lines = response.lines if hasattr(response, "lines") else response
    if not isinstance(lines, (list, tuple)):
        return [lines]
    return list(lines)


def _parse_uid(lines: list[object]) -> int | None:
    for item in lines:
        text = item.decode(errors="replace") if isinstance(item, bytes) else str(item)
        match = re.search(r"\bUID\s+(\d+)\b", text)
        if match:
            return int(match.group(1))
    return None


def _parse_exists_counts(lines: list[object]) -> list[int]:
    counts: list[int] = []
    for item in lines:
        text = item.decode(errors="replace") if isinstance(item, bytes) else str(item)
        match = re.search(r"(\d+)\s+EXISTS", text)
        if match:
            counts.append(int(match.group(1)))
    return counts


def _format_imap_since(hours: int) -> str:
    since = datetime.now(UTC) - timedelta(hours=hours)
    return since.strftime("%d-%b-%Y")


async def _search_sequences_since(client: aioimaplib.IMAP4_SSL, hours: int) -> list[str]:
    since = _format_imap_since(hours)
    criteria = ["SINCE", since]
    if settings.IMAP_SWEEP_UNSEEN_ONLY:
        criteria.append("UNSEEN")
    logger.info(
        "imap.sweep_search_start",
        since=since,
        lookback_hours=hours,
        unseen_only=settings.IMAP_SWEEP_UNSEEN_ONLY,
    )
    _, response = await client.search(*criteria)
    lines = _response_lines(response)
    sequences: list[int] = []
    for item in lines:
        text = item.decode(errors="replace") if isinstance(item, bytes) else str(item)
        for token in re.findall(r"\b\d+\b", text):
            sequences.append(int(token))
    unique = [str(seq) for seq in sorted(set(sequences))]
    logger.info(
        "imap.sweep_search_done",
        since=since,
        sequence_count=len(unique),
        unseen_only=settings.IMAP_SWEEP_UNSEEN_ONLY,
    )
    return unique


async def _fetch_and_process(
    client: aioimaplib.IMAP4_SSL, message_id: str, *, by_uid: bool = False
) -> Optional[dict]:
    """Fetch a single message and return a normalized envelope dict."""
    logger.info("imap.fetch_start", message_id=message_id, by_uid=by_uid)
    if by_uid:
        _, response = await client.uid("FETCH", message_id, "(UID BODY.PEEK[])")
    else:
        _, response = await client.fetch(message_id, "(UID BODY.PEEK[])")

    # aioimaplib returns protocol metadata and payload chunks in the same list.
    # Pick the RFC822 payload, avoiding small terminators like b")".
    lines = _response_lines(response)
    uid = _parse_uid(lines)

    payload_lines = [bytes(line) for line in lines if isinstance(line, (bytes, bytearray))]
    candidates = [
        line
        for line in payload_lines
        if len(line) > 20
        and line.strip() != b")"
        and not re.match(rb"^\d+\s+FETCH\s+", line)
        and not line.startswith(b" FLAGS ")
        and line != b"Success"
        and (
            b"\r\n\r\n" in line
            or b"\n\n" in line
            or b"Subject:" in line
            or b"From:" in line
        )
    ]
    raw_email: Optional[bytes] = max(candidates, key=len) if candidates else None

    # Some servers split the literal into bytearray chunks, while others keep
    # metadata and payload together. The fallback keeps that second shape alive.
    if raw_email is None:
        candidates = [
            line
            for line in payload_lines
            if len(line) > 20
            and (
                b"\r\n\r\n" in line
                or b"\n\n" in line
                or b"Subject:" in line
                or b"From:" in line
            )
        ]
        raw_email = max(candidates, key=len) if candidates else None

    if raw_email is None:
        logger.warning("imap.fetch_failed", message_id=message_id, by_uid=by_uid, uid=uid)
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
    envelope["imap_uid"] = uid
    logger.info(
        "imap.fetch_done",
        message_id=message_id,
        by_uid=by_uid,
        uid=uid,
        sender=sender[:40],
        subject=subject[:60],
    )
    return envelope


async def _insert_incident(envelope: dict) -> bool:
    """Insert a normalized envelope into the incidents table."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        duplicate_id = await conn.fetchval(
            """
            SELECT id
            FROM incidents
            WHERE source = 'email_imap'
              AND coalesce(sender, '') = $1
              AND coalesce(subject, '') = $2
              AND coalesce(body, '') = $3
              AND received_at > now() - interval '2 days'
            LIMIT 1
            """,
            envelope["sender"],
            envelope["subject"],
            envelope["body"],
        )
        if duplicate_id:
            logger.info(
                "imap.incident_duplicate_skipped",
                duplicate_id=str(duplicate_id),
                imap_uid=envelope.get("imap_uid"),
                subject=envelope["subject"][:60],
            )
            return False

        await conn.execute(
            """
            INSERT INTO incidents (source, sender, subject, body, iocs, status)
            VALUES ($1, $2, $3, $4, $5, 'triaging')
            """,
            envelope["source"],
            envelope["sender"],
            envelope["subject"],
            envelope["body"],
            json.dumps(envelope["iocs"]),
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
        imap_uid=envelope.get("imap_uid"),
        sender=envelope["sender"][:40],
        subject=envelope["subject"][:60],
    )
    return True


@retry(
    retry=retry_if_exception_type(Exception),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=4, max=120),
)
async def _connect_imap() -> aioimaplib.IMAP4_SSL:
    """Connect and authenticate to the IMAP server. Retries on failure."""
    global _last_exists_count

    client = aioimaplib.IMAP4_SSL(
        host=settings.IMAP_HOST,
        port=settings.IMAP_PORT,
    )
    await client.wait_hello_from_server()
    await client.login(settings.IMAP_USERNAME, settings.IMAP_PASSWORD)
    _, response = await client.select(settings.IMAP_MAILBOX)
    exists_counts = _parse_exists_counts(_response_lines(response))
    if exists_counts:
        _last_exists_count = max(exists_counts)
    logger.info(
        "imap.connected",
        host=settings.IMAP_HOST,
        mailbox=settings.IMAP_MAILBOX,
        exists_count=_last_exists_count,
    )
    return client


async def _process_uid_sweep(client: aioimaplib.IMAP4_SSL, *, lookback_hours: int) -> int:
    """Fetch recent UIDs through the same normalize/insert path used by IDLE."""
    global _last_seen_uid

    inserted = 0
    for sequence in await _search_sequences_since(client, lookback_hours):
        envelope = await _fetch_and_process(client, sequence)
        uid = envelope.get("imap_uid") if envelope else None
        if uid is not None and _last_seen_uid is not None and uid <= _last_seen_uid:
            logger.info("imap.sweep_uid_skipped", uid=uid, last_seen_uid=_last_seen_uid)
            continue
        if envelope and await _insert_incident(envelope):
            inserted += 1
        if uid is not None:
            _last_seen_uid = max(_last_seen_uid or 0, uid)

    logger.info(
        "imap.sweep_done",
        inserted=inserted,
        last_seen_uid=_last_seen_uid,
        lookback_hours=lookback_hours,
    )
    return inserted


async def _process_exists_range(
    client: aioimaplib.IMAP4_SSL,
    exists_counts: list[int],
) -> int:
    """Fetch only the new sequence numbers indicated by an IDLE EXISTS push."""
    global _last_exists_count, _last_seen_uid

    if not exists_counts:
        return 0

    current_exists_count = max(exists_counts)
    previous_exists_count = _last_exists_count
    if previous_exists_count is None:
        message_numbers = sorted(set(exists_counts))
    else:
        message_numbers = list(range(previous_exists_count + 1, current_exists_count + 1))

    inserted = 0
    for message_num in message_numbers:
        envelope = await _fetch_and_process(client, str(message_num))
        uid = envelope.get("imap_uid") if envelope else None
        if uid is not None and _last_seen_uid is not None and uid <= _last_seen_uid:
            logger.info("imap.exists_uid_skipped", uid=uid, last_seen_uid=_last_seen_uid)
            continue
        if envelope and await _insert_incident(envelope):
            inserted += 1
        if uid is not None:
            _last_seen_uid = max(_last_seen_uid or 0, uid)

    _last_exists_count = max(_last_exists_count or 0, current_exists_count)
    logger.info(
        "imap.exists_range_done",
        inserted=inserted,
        message_count=len(message_numbers),
        previous_exists_count=previous_exists_count,
        current_exists_count=current_exists_count,
        last_seen_uid=_last_seen_uid,
    )
    return inserted


async def sweep_last_day() -> int:
    """One-shot recent inbox sweep for demo catch-up and IDLE verification."""
    if not settings.IMAP_USERNAME or not settings.IMAP_PASSWORD:
        logger.warning("imap.no_credentials — skipping IMAP sweep")
        return 0

    client: Optional[aioimaplib.IMAP4_SSL] = None
    try:
        client = await _connect_imap()
        return await _process_uid_sweep(
            client,
            lookback_hours=settings.IMAP_SWEEP_LOOKBACK_HOURS,
        )
    finally:
        if client:
            try:
                await client.logout()
            except Exception:
                pass


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
            if settings.IMAP_STARTUP_SWEEP_ENABLED:
                await _process_uid_sweep(
                    client,
                    lookback_hours=settings.IMAP_SWEEP_LOOKBACK_HOURS,
                )

            while True:
                # Enter IDLE and wait for EXISTS (new message)
                logger.info("imap.idle_enter", timeout=settings.IMAP_IDLE_TIMEOUT_SECONDS)
                await client.idle_start(timeout=settings.IMAP_IDLE_TIMEOUT_SECONDS)
                response = await client.wait_server_push(
                    timeout=settings.IMAP_IDLE_TIMEOUT_SECONDS,
                )
                responses = _response_lines(response)
                logger.info(
                    "imap.idle_push",
                    responses=[
                        item.decode(errors="replace") if isinstance(item, bytes) else str(item)
                        for item in responses
                    ],
                )
                exists_counts = _parse_exists_counts(responses)
                client.idle_done()
                logger.info("imap.idle_done", exists_counts=exists_counts)

                if exists_counts:
                    await _process_exists_range(client, exists_counts)

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
