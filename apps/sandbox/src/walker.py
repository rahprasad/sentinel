"""Playwright walker.

Drives a headless Chromium against a scam URL, screenshotting each step,
filling forms with well-formed decoys, and detecting where the funnel
actually terminates. The output drives the "what they wanted" card.

Container guarantees (delivered by the Dockerfile, restated here for safety):
- ephemeral filesystem
- no mounted credentials
- network egress only
- one walk per container lifetime is fine if memory grows
"""
from __future__ import annotations

import asyncio
from typing import Optional

import structlog
from playwright.async_api import (
    Browser,
    BrowserContext,
    ElementHandle,
    Page,
    TimeoutError as PlaywrightTimeout,
    async_playwright,
)

from . import actionbook
from .config import settings
from .form_filler import canonical_label, decoy_for
from .funnel import detect as detect_funnel, is_terminal_domain
from .models import WalkResult, WalkStep
from .storage import upload_png

log = structlog.get_logger("walker")

_SUBMIT_TEXT_PATTERN = (
    "continue|submit|next|pay|verify|confirm|claim|"
    "redeem|unlock|proceed|finish|complete"
)


async def walk(url: str, incident_id: str) -> WalkResult:
    """Top-level walker entry. Wraps everything in a per-walk timeout."""
    try:
        return await asyncio.wait_for(
            _walk_inner(url, incident_id),
            timeout=settings.walker_timeout_seconds,
        )
    except asyncio.TimeoutError:
        log.warning("walker_timeout", url=url, incident_id=incident_id)
        return WalkResult(
            funnel_terminus="error",
            error=f"timeout after {settings.walker_timeout_seconds}s",
        )
    except Exception as exc:
        log.exception("walker_unhandled", url=url, error=str(exc))
        return WalkResult(funnel_terminus="error", error=str(exc))


async def _walk_inner(url: str, incident_id: str) -> WalkResult:
    steps: list[WalkStep] = []
    harvested: set[str] = set()
    final_url = url

    async with async_playwright() as pw:
        browser = await _open_browser(pw)
        try:
            context = await _new_context(browser)
            page = await context.new_page()

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            except PlaywrightTimeout:
                pass  # we'll still try to interact with whatever loaded

            for step_idx in range(settings.walker_max_steps):
                step, fields_this_page = await _capture_step(page, incident_id, step_idx)
                steps.append(step)
                harvested.update(fields_this_page)
                final_url = step.url

                if is_terminal_domain(step.url):
                    break

                # Fill forms then click the most submit-looking thing.
                await _fill_visible_forms(page, step.url)
                clicked = await _click_submit(page, step.url)
                if not clicked:
                    break

                # Give the page a beat to navigate / show next form.
                try:
                    await page.wait_for_load_state(
                        "domcontentloaded", timeout=8000
                    )
                except PlaywrightTimeout:
                    pass
                await page.wait_for_timeout(800)

            return WalkResult(
                steps=steps,
                final_url=final_url,
                harvested_fields=sorted(harvested),
                funnel_terminus=detect_funnel(final_url, harvested),
            )
        finally:
            await browser.close()


async def _open_browser(pw) -> Browser:
    """Connect to Bright Data's Scraping Browser if configured, else local Chromium.

    Bright Data Scraping Browser:
    - residential IPs, anti-bot evasion, per-session rotation
    - Playwright connects over CDP, not a local launch
    - session ends when we close the browser
    """
    ws = settings.bright_data_browser_ws.strip()
    if ws:
        log.info("walker_backend", backend="bright_data_scraping_browser")
        return await pw.chromium.connect_over_cdp(ws)
    log.info("walker_backend", backend="local_chromium")
    return await pw.chromium.launch(headless=True, args=["--no-sandbox"])


async def _new_context(browser: Browser) -> BrowserContext:
    # Bright Data Scraping Browser manages UA / fingerprint on its end —
    # the explicit user_agent is a no-op there but harmless. Locally it matters.
    return await browser.new_context(
        user_agent=settings.walker_user_agent,
        viewport={"width": 1280, "height": 800},
        java_script_enabled=True,
        locale="en-US",
    )


async def _capture_step(
    page: Page, incident_id: str, step_idx: int
) -> tuple[WalkStep, set[str]]:
    # Screenshot
    try:
        png = await page.screenshot(full_page=False)
    except Exception:
        png = b""
    screenshot_url = (
        await upload_png(png, incident_id=incident_id, step_idx=step_idx)
        if png
        else ""
    )

    # Form-field inventory + canonical labels.
    raw_fields, canonical = await _inventory_inputs(page)

    # Trim a bit of page text — useful for the synthesizer prompt.
    try:
        page_text = (await page.inner_text("body"))[:1200]
    except Exception:
        page_text = ""

    step = WalkStep(
        screenshot_url=screenshot_url,
        url=page.url,
        form_fields=raw_fields,
        page_text=page_text,
    )
    return step, canonical


async def _inventory_inputs(page: Page) -> tuple[list[str], set[str]]:
    """Snapshot inputs. Returns (raw display strings, canonical labels)."""
    raw: list[str] = []
    canonical: set[str] = set()

    handles = await page.query_selector_all("input, select, textarea")
    for h in handles:
        try:
            if not await h.is_visible():
                continue
        except Exception:
            continue
        name = await h.get_attribute("name") or ""
        ftype = await h.get_attribute("type") or "text"
        placeholder = await h.get_attribute("placeholder") or ""
        if ftype in ("hidden", "submit", "button", "image", "reset"):
            continue

        display = name or placeholder or ftype
        raw.append(display)

        lbl = canonical_label(name, ftype, placeholder)
        if lbl:
            canonical.add(lbl)

    return raw, canonical


async def _fill_visible_forms(page: Page, page_url: str) -> None:
    overrides = await actionbook.lookup_field_selectors(page_url)

    # Actionbook-driven targeted fills (most reliable when present).
    for label, selector in overrides.items():
        try:
            await page.fill(selector, decoy_for(label, label=label), timeout=1500)
        except Exception:
            continue

    # Heuristic fill for every other visible input.
    handles = await page.query_selector_all("input, textarea")
    for h in handles:
        try:
            if not await h.is_visible():
                continue
            ftype = await h.get_attribute("type") or "text"
            if ftype in ("hidden", "submit", "button", "image", "reset", "file"):
                continue
            name = await h.get_attribute("name") or ""
            placeholder = await h.get_attribute("placeholder") or ""
            value = decoy_for(name, ftype, placeholder)
            await h.fill(value, timeout=1500)
        except Exception:
            continue


async def _click_submit(page: Page, page_url: str) -> bool:
    # Actionbook override wins if present.
    selector = await actionbook.lookup_submit_selector(page_url)
    if selector and await _try_click(page, selector):
        return True

    # Heuristic: a submit-y button.
    candidates: list[ElementHandle] = []
    candidates.extend(await page.query_selector_all('button[type="submit"]'))
    candidates.extend(await page.query_selector_all('input[type="submit"]'))
    candidates.extend(await page.query_selector_all("button"))
    candidates.extend(await page.query_selector_all('a[role="button"], a.btn, a.button'))

    for el in candidates:
        try:
            if not await el.is_visible():
                continue
            text = (await el.inner_text()).strip().lower() if el else ""
        except Exception:
            text = ""

        if not text:
            continue
        if _looks_like_submit(text):
            try:
                await el.click(timeout=2000)
                return True
            except Exception:
                continue

    # Last-ditch — submit the first form.
    form = await page.query_selector("form")
    if form:
        try:
            await form.evaluate("(f) => f.requestSubmit ? f.requestSubmit() : f.submit()")
            return True
        except Exception:
            return False
    return False


async def _try_click(page: Page, selector: str) -> bool:
    try:
        await page.click(selector, timeout=2000)
        return True
    except Exception:
        return False


def _looks_like_submit(text: str) -> bool:
    import re

    return bool(re.search(_SUBMIT_TEXT_PATTERN, text, flags=re.IGNORECASE))


# Tiny adapter used by main.py — Optional kept for forwards compat
async def walk_optional(url: Optional[str], incident_id: str) -> Optional[WalkResult]:
    if not url:
        return None
    return await walk(url, incident_id)
