"use client";

import { usePolling } from "@/hooks/use-polling";
import {
  fetchAgentActivity,
  type AgentEvent,
  type AgentStats,
} from "@/lib/agent-activity";

const POLL_MS = 1500;

const AGENT_COLORS: Record<string, string> = {
  "imap-watcher": "bg-cyan-900/60 text-cyan-200 border-cyan-700/60",
  triage: "bg-sky-900/60 text-sky-200 border-sky-700/60",
  orchestrator: "bg-slate-700/60 text-slate-200 border-slate-600/60",
  "domain-intel": "bg-violet-900/60 text-violet-200 border-violet-700/60",
  "sandbox-walker": "bg-emerald-900/60 text-emerald-200 border-emerald-700/60",
  synthesizer: "bg-amber-900/60 text-amber-200 border-amber-700/60",
};

const EVENT_DOT: Record<string, string> = {
  started: "bg-sky-400 animate-pulse",
  completed: "bg-emerald-400",
  failed: "bg-rose-500",
  fixture_used: "bg-amber-400",
  synthesizer_fallback: "bg-amber-400",
  incident_ingested: "bg-cyan-400 animate-pulse",
  ioc_cache_hit: "bg-emerald-300",
};

export default function AgentActivityPanel() {
  const { data, error } = usePolling(() => fetchAgentActivity(30), POLL_MS);

  if (error) {
    return (
      <div className="rounded-xl border border-rose-800/60 bg-rose-950/30 p-5 text-sm text-rose-200">
        Couldn&apos;t reach the investigation service: {error.message}
      </div>
    );
  }

  const agents: AgentStats[] = data?.agents ?? [];
  const events: AgentEvent[] = data?.events ?? [];
  const totals = data?.totals;
  const totalInFlight = agents.reduce((acc, a) => acc + a.in_flight, 0);

  return (
    <div className="rounded-xl border border-[var(--card-border)] bg-[var(--card)] p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-[var(--muted)] uppercase tracking-wider">
          Live agent activity
        </h2>
        <div className="flex items-center gap-3 text-xs text-[var(--muted)]">
          <span className="inline-flex items-center gap-1.5">
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                totalInFlight > 0
                  ? "bg-emerald-400 animate-pulse"
                  : "bg-slate-600"
              }`}
            />
            {totalInFlight > 0 ? `${totalInFlight} running` : "idle"}
          </span>
          {totals ? (
            <span>
              {totals.investigations_completed} done · {totals.events_captured}{" "}
              events
            </span>
          ) : null}
        </div>
      </div>

      {agents.length === 0 ? (
        <p className="text-sm text-[var(--muted)] py-6 text-center">
          No agent runs yet. They&apos;ll appear here as soon as an incident
          starts investigating.
        </p>
      ) : (
        <>
          <AgentStatsGrid agents={agents} />
          <EventStream events={events} />
        </>
      )}
    </div>
  );
}

function AgentStatsGrid({ agents }: { agents: AgentStats[] }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 gap-2 mb-5">
      {agents.map((a) => {
        const palette =
          AGENT_COLORS[a.agent] ??
          "bg-slate-800/50 text-slate-200 border-slate-700";
        return (
          <div
            key={a.agent}
            className={`rounded-lg border px-3 py-2.5 ${palette}`}
          >
            <div className="flex items-center justify-between text-xs">
              <span className="font-mono">{a.agent}</span>
              {a.in_flight > 0 ? (
                <span className="inline-flex items-center gap-1 text-[10px]">
                  <span className="h-1 w-1 rounded-full bg-current animate-pulse" />
                  {a.in_flight} live
                </span>
              ) : null}
            </div>
            <div className="mt-1 text-xs opacity-80 flex justify-between">
              <span>
                ✓ {a.completed}
                {a.failed > 0 ? <span className="ml-1.5">✗ {a.failed}</span> : null}
                {a.fixture_used > 0 ? (
                  <span className="ml-1.5">⟲ {a.fixture_used}</span>
                ) : null}
              </span>
              {a.avg_latency_ms !== null ? (
                <span className="opacity-70">
                  {formatLatency(a.avg_latency_ms)}
                </span>
              ) : null}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function EventStream({ events }: { events: AgentEvent[] }) {
  if (events.length === 0) return null;
  return (
    <div>
      <p className="text-[10px] uppercase tracking-wider text-[var(--muted)] mb-2">
        Recent events
      </p>
      <ol className="max-h-[280px] overflow-y-auto space-y-1.5 pr-1">
        {events.map((ev, i) => (
          <li
            key={`${ev.timestamp}-${i}`}
            className="flex items-start gap-2 text-xs"
          >
            <span
              className={`mt-1 h-1.5 w-1.5 shrink-0 rounded-full ${
                EVENT_DOT[ev.event] ?? "bg-slate-500"
              }`}
            />
            <span className="font-mono text-[var(--muted)] tabular-nums">
              {formatTime(ev.timestamp)}
            </span>
            <span className="font-mono">{ev.agent}</span>
            <span className="text-[var(--muted)]">{ev.event}</span>
            {ev.duration_ms !== null ? (
              <span className="ml-auto tabular-nums text-[var(--muted)]">
                {formatLatency(ev.duration_ms)}
              </span>
            ) : null}
          </li>
        ))}
      </ol>
    </div>
  );
}

function formatLatency(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 10_000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.round(ms / 1000)}s`;
}

function formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString("en-US", {
      hour12: false,
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return iso.slice(11, 19);
  }
}
