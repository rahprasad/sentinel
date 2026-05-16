"""Screenshot storage.

Tries S3 first if credentials are present, otherwise saves to a local dir
and returns a URL served by the sandbox FastAPI app. The local fallback is
what makes the walker testable on a dev machine without provisioning S3.
"""
from __future__ import annotations

import asyncio
import os
import uuid
from pathlib import Path

from .config import settings

_local_dir_initialised = False


def _ensure_local_dir() -> Path:
    global _local_dir_initialised
    d = Path(settings.local_screenshot_dir)
    if not _local_dir_initialised:
        d.mkdir(parents=True, exist_ok=True)
        _local_dir_initialised = True
    return d


async def upload_png(data: bytes, *, incident_id: str, step_idx: int) -> str:
    """Store a PNG and return a publicly-resolvable URL."""
    key = f"{incident_id}/step-{step_idx:02d}-{uuid.uuid4().hex[:8]}.png"

    if _s3_configured():
        return await _upload_s3(data, key)
    return await _write_local(data, key)


def _s3_configured() -> bool:
    return bool(
        settings.s3_endpoint
        and settings.s3_access_key_id
        and settings.s3_secret_access_key
    )


async def _upload_s3(data: bytes, key: str) -> str:
    import boto3  # imported lazily to keep local-only dev fast

    def _put() -> str:
        client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
        )
        client.put_object(
            Bucket=settings.s3_bucket,
            Key=key,
            Body=data,
            ContentType="image/png",
        )
        prefix = settings.s3_public_url_prefix.rstrip("/")
        if prefix:
            return f"{prefix}/{key}"
        return f"{settings.s3_endpoint.rstrip('/')}/{settings.s3_bucket}/{key}"

    return await asyncio.get_event_loop().run_in_executor(None, _put)


async def _write_local(data: bytes, key: str) -> str:
    d = _ensure_local_dir()
    out_path = d / key
    out_path.parent.mkdir(parents=True, exist_ok=True)

    def _write() -> None:
        with open(out_path, "wb") as f:
            f.write(data)

    await asyncio.get_event_loop().run_in_executor(None, _write)
    prefix = settings.local_screenshot_url_prefix.rstrip("/")
    return f"{prefix}/{key}"


def local_file_for(url_path: str) -> Path | None:
    """Resolve a /screenshots/... URL path back to the on-disk file."""
    d = Path(settings.local_screenshot_dir)
    candidate = (d / url_path.lstrip("/")).resolve()
    if not candidate.is_file():
        return None
    # Guard against path traversal
    if not str(candidate).startswith(str(d.resolve()) + os.sep):
        return None
    return candidate
