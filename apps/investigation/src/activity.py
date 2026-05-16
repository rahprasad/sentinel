"""In-process activity log for the investigation tier.

Captures structured agent events (start/complete/fixture-used/failed) so the
dashboard can render a live view of what each agent is doing. Holds the last
N events in a thread-safe deque — no DB write, no external dependency.

Counts persist for the lifetime of the process. AgentField's control plane
gives the same information with much more depth, but this gives Person A's
existing web dashboard a zero-coupling way to surface activity right now.
"""
from __future__ import annotations

import asyncio
import time
from collections import Counter, deque
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Optional

MAX_EVENTS = 100


@dataclass
class AgentEvent:
    timestamp: str
    incident_id: Optional[str]
    agent: str
    event: str  # "started" | "completed" | "failed" | "fixture_used" | "synthesizer_fallback"
    duration_ms: Optional[int] = None
    details: dict[str, Any] = field(default_factory=dict)


class _ActivityLog:
    def __init__(self, max_events: int = MAX_EVENTS) -> None:
        self._events: deque[AgentEvent] = deque(maxlen=max_events)
        self._counters: Counter[str] = Counter()
        self._latencies_ms: dict[str, list[int]] = {}
        self._in_flight: dict[str, int] = {}
        self._lock = asyncio.Lock()

    async def add(self, event: AgentEvent) -> None:
        async with self._lock:
            self._events.appendleft(event)
            self._counters[f"{event.agent}.{event.event}"] += 1
            if event.event == "started":
                self._in_flight[event.agent] = self._in_flight.get(event.agent, 0) + 1
            elif event.event in ("completed", "failed"):
                self._in_flight[event.agent] = max(0, self._in_flight.get(event.agent, 0) - 1)
            if event.duration_ms is not None:
                self._latencies_ms.setdefault(event.agent, []).append(event.duration_ms)

    def snapshot(self, limit: int = 50) -> dict[str, Any]:
        events = list(self._events)[:limit]
        agents = sorted(
            {ev.agent for ev in self._events} | set(self._in_flight.keys())
        )
        agent_stats = []
        for agent in agents:
            samples = self._latencies_ms.get(agent, [])
            agent_stats.append(
                {
                    "agent": agent,
                    "in_flight": self._in_flight.get(agent, 0),
                    "completed": self._counters.get(f"{agent}.completed", 0),
                    "failed": self._counters.get(f"{agent}.failed", 0),
                    "fixture_used": self._counters.get(f"{agent}.fixture_used", 0),
                    "avg_latency_ms": int(sum(samples) / len(samples)) if samples else None,
                    "p95_latency_ms": int(sorted(samples)[int(0.95 * len(samples))]) if len(samples) >= 5 else None,
                }
            )
        return {
            "events": [_event_to_json(ev) for ev in events],
            "agents": agent_stats,
            "totals": {
                "events_captured": sum(self._counters.values()),
                "investigations_completed": self._counters.get("orchestrator.completed", 0),
                "investigations_failed": self._counters.get("orchestrator.failed", 0),
            },
        }


_log = _ActivityLog()


def _event_to_json(ev: AgentEvent) -> dict[str, Any]:
    return {
        "timestamp": ev.timestamp,
        "incident_id": ev.incident_id,
        "agent": ev.agent,
        "event": ev.event,
        "duration_ms": ev.duration_ms,
        "details": ev.details,
    }


async def record(
    agent: str,
    event: str,
    incident_id: Optional[str] = None,
    duration_ms: Optional[int] = None,
    **details: Any,
) -> None:
    await _log.add(
        AgentEvent(
            timestamp=datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            incident_id=incident_id,
            agent=agent,
            event=event,
            duration_ms=duration_ms,
            details=details,
        )
    )


def snapshot(limit: int = 50) -> dict[str, Any]:
    """Caller-side getter — must not be awaited."""
    return _log.snapshot(limit=limit)


@asynccontextmanager
async def track(agent: str, incident_id: Optional[str] = None, **details: Any) -> AsyncIterator[None]:
    """Wrap a unit of work: emit started+completed (or failed) with timing."""
    started = time.monotonic()
    await record(agent, "started", incident_id=incident_id, **details)
    try:
        yield
    except Exception as exc:
        await record(
            agent,
            "failed",
            incident_id=incident_id,
            duration_ms=int((time.monotonic() - started) * 1000),
            error=str(exc),
        )
        raise
    await record(
        agent,
        "completed",
        incident_id=incident_id,
        duration_ms=int((time.monotonic() - started) * 1000),
    )
