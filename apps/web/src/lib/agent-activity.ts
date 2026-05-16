// Types + fetcher for the investigation service's /agent-activity endpoint.

const INVESTIGATION_URL =
  process.env.NEXT_PUBLIC_INVESTIGATION_URL ?? "http://localhost:8002";

export type AgentName =
  | "orchestrator"
  | "triage"
  | "domain-intel"
  | "sandbox-walker"
  | "synthesizer";

export type AgentEventType =
  | "started"
  | "completed"
  | "failed"
  | "fixture_used"
  | "synthesizer_fallback";

export interface AgentEvent {
  timestamp: string;
  incident_id: string | null;
  agent: AgentName | string;
  event: AgentEventType | string;
  duration_ms: number | null;
  details: Record<string, unknown>;
}

export interface AgentStats {
  agent: string;
  in_flight: number;
  completed: number;
  failed: number;
  fixture_used: number;
  avg_latency_ms: number | null;
  p95_latency_ms: number | null;
}

export interface AgentActivitySnapshot {
  events: AgentEvent[];
  agents: AgentStats[];
  totals: {
    events_captured: number;
    investigations_completed: number;
    investigations_failed: number;
  };
}

export async function fetchAgentActivity(
  limit = 30,
): Promise<AgentActivitySnapshot> {
  const res = await fetch(
    `${INVESTIGATION_URL}/agent-activity?limit=${limit}`,
    { cache: "no-store" },
  );
  if (!res.ok) throw new Error(`agent-activity: ${res.status}`);
  return res.json();
}
