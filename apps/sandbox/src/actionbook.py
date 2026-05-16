"""Actionbook integration over MCP (Model Context Protocol).

Actionbook publishes pre-computed action manuals and verified DOM selectors
for common scam templates. We use it from the walker before clicking, so
when the heuristic ("find a button labelled /continue|next|pay/") would
miss, the verified selector wins.

Transport: MCP Streamable HTTP at edge.actionbook.dev/mcp (no auth in beta).
Strategy: connect on demand → list tools once → fuzzy-pick the best tool
name for each intent → cache the mapping. Every failure mode collapses to
`None` so `walker.py` falls back to its heuristic without us in the way.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Optional

import structlog

from .config import settings

log = structlog.get_logger("actionbook")

# Cached mapping from our intent labels to discovered Actionbook tool names.
# Populated lazily on first successful list_tools().
_tool_for_intent: dict[str, Optional[str]] = {}
_tool_for_intent_lock = asyncio.Lock()

# Keywords used to fuzz-match Actionbook tool names. We don't know the exact
# tool names ahead of time, so we score each tool's name+description against
# these keyword sets and pick the highest scorer per intent.
_INTENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "submit": ("submit", "primary", "cta", "action", "next", "continue"),
    "fields": ("field", "form", "input", "selectors", "elements"),
    "manual": ("manual", "playbook", "actions", "page"),
}


async def lookup_submit_selector(url: str) -> Optional[str]:
    """Return a CSS selector for the submit button on this URL, or None."""
    payload = await _resolve(url, intent="submit")
    return _extract_selector(payload, keys=("submit_selector", "primary_action_selector", "selector"))


async def lookup_field_selectors(url: str) -> dict[str, str]:
    """Return {canonical_label: CSS selector} for form fields on this URL, or {}."""
    payload = await _resolve(url, intent="fields")
    return _extract_field_map(payload)


# ─── MCP plumbing ───────────────────────────────────────────────────────────


async def _resolve(url: str, *, intent: str) -> Optional[dict[str, Any]]:
    if not settings.actionbook_mcp_url:
        return None
    try:
        return await asyncio.wait_for(
            _call_actionbook(url, intent),
            timeout=settings.actionbook_timeout_seconds,
        )
    except asyncio.TimeoutError:
        log.warning("actionbook_timeout", url=url, intent=intent)
        return None
    except Exception as exc:
        log.warning("actionbook_error", url=url, intent=intent, error=str(exc))
        return None


async def _call_actionbook(url: str, intent: str) -> Optional[dict[str, Any]]:
    # Lazy imports — the mcp package is heavy and only loaded when we need it.
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    async with streamablehttp_client(settings.actionbook_mcp_url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tool_name = await _tool_name_for(session, intent)
            if not tool_name:
                return None

            result = await session.call_tool(name=tool_name, arguments={"url": url})
            return _decode_tool_result(result)


async def _tool_name_for(session, intent: str) -> Optional[str]:
    async with _tool_for_intent_lock:
        if intent in _tool_for_intent:
            return _tool_for_intent[intent]

        listing = await session.list_tools()
        tools = getattr(listing, "tools", listing) or []
        chosen = _best_tool(tools, intent)
        _tool_for_intent[intent] = chosen
        if chosen:
            log.info("actionbook_tool_bound", intent=intent, tool=chosen)
        else:
            log.warning("actionbook_no_tool_for_intent", intent=intent, n_tools=len(tools))
        return chosen


def _best_tool(tools: list[Any], intent: str) -> Optional[str]:
    keywords = _INTENT_KEYWORDS.get(intent, ())
    best_name: Optional[str] = None
    best_score = 0
    for tool in tools:
        name = (getattr(tool, "name", "") or "").lower()
        description = (getattr(tool, "description", "") or "").lower()
        haystack = f"{name} {description}"
        score = sum(1 for kw in keywords if kw in haystack)
        if score > best_score:
            best_score = score
            best_name = getattr(tool, "name", None)
    return best_name if best_score > 0 else None


def _decode_tool_result(result: Any) -> Optional[dict[str, Any]]:
    """MCP tool results carry a list of content blocks. We try JSON-parsing the first text block."""
    content = getattr(result, "content", None) or []
    for block in content:
        text = getattr(block, "text", None)
        if not text:
            continue
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return data
            if isinstance(data, list) and data and isinstance(data[0], dict):
                return data[0]
        except json.JSONDecodeError:
            continue
    # As a last resort, fall back to structured payload if the SDK exposed it directly.
    structured = getattr(result, "structuredContent", None) or getattr(result, "structured_content", None)
    if isinstance(structured, dict):
        return structured
    return None


def _extract_selector(payload: Optional[dict[str, Any]], *, keys: tuple[str, ...]) -> Optional[str]:
    if not payload:
        return None
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    # Nested under "submit", "actions", etc.
    for nested_key in ("submit", "primary", "actions"):
        nested = payload.get(nested_key)
        if isinstance(nested, dict):
            inner = _extract_selector(nested, keys=keys + ("css", "value"))
            if inner:
                return inner
    return None


def _extract_field_map(payload: Optional[dict[str, Any]]) -> dict[str, str]:
    if not payload:
        return {}
    raw = payload.get("fields") or payload.get("inputs") or payload.get("selectors")
    if not isinstance(raw, dict):
        return {}
    return {
        str(label): selector
        for label, selector in raw.items()
        if isinstance(selector, str) and selector.strip()
    }
