"""Module loaded by `uvicorn src.main:app`.

Imports each pipeline module so AgentField's @reasoner / @skill decorators
run at import time and register handlers with the control plane before the
server starts accepting requests.
"""
from __future__ import annotations

from .agent import app

# Side-effect imports — decorator registration happens here.
from . import domain_intel  # noqa: F401
from . import sandbox_client  # noqa: F401
from . import synthesizer  # noqa: F401
from . import orchestrator  # noqa: F401

__all__ = ["app"]
