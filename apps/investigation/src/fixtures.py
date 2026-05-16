"""Walker fixture loader.

Two ways fixtures get used:

1. `settings.fixture_mode = True` — every incident loads fixtures keyed by
   triage.scam_type. Used when the live walker is unreliable in a demo room.

2. Live walker errored — orchestrator falls back to fixtures so the card
   still ships.

Fixture files live at `fixtures/walks/{scam_type}.json` and are produced by
`scripts/record_fixtures.py`.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import structlog

from .config import settings
from .models import WalkResult

log = structlog.get_logger("fixtures")


def load_walk(scam_type: str) -> Optional[WalkResult]:
    if not scam_type:
        return None
    key = _normalise(scam_type)
    path = Path(settings.fixtures_dir) / f"{key}.json"
    if not path.exists():
        log.info("fixture_miss", scam_type=scam_type, path=str(path))
        return None
    try:
        data = json.loads(path.read_text())
        return WalkResult.model_validate(data)
    except Exception as exc:
        log.warning("fixture_invalid", path=str(path), error=str(exc))
        return None


def _normalise(scam_type: str) -> str:
    return scam_type.strip().lower().replace(" ", "-").replace("_", "-")
