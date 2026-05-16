/** API fetch helpers for the Sentinel backend. */

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface Incident {
  id: string;
  received_at: string;
  source: string;
  sender: string;
  subject: string;
  body: string;
  iocs: {
    urls: string[];
    phones: string[];
    wallets: string[];
    handles: string[];
  };
  triage: {
    is_scam: boolean;
    confidence: number;
    scam_type: string;
    tells: { span: string; why: string }[];
    reasoning: string;
  } | null;
  status: "triaging" | "investigating" | "done" | "safe";
  investigation: Record<string, unknown> | null;
  screenshots: string[];
  estimated_loss_usd: number | null;
}

export interface MonitoringSource {
  source: string;
  last_check: string | null;
  state: "active" | "error" | "paused";
  items_scanned_total: number;
  error_message: string | null;
}

export interface Stats {
  blocked_count: number;
  estimated_savings_usd: number;
  scanned_today: number;
}

export async function fetchIncidents(
  limit = 50,
  offset = 0
): Promise<{ incidents: Incident[]; count: number }> {
  const res = await fetch(
    `${API_URL}/incidents?limit=${limit}&offset=${offset}`
  );
  if (!res.ok) throw new Error(`fetchIncidents: ${res.status}`);
  return res.json();
}

export async function fetchIncident(id: string): Promise<Incident> {
  const res = await fetch(`${API_URL}/incidents/${id}`);
  if (!res.ok) throw new Error(`fetchIncident: ${res.status}`);
  return res.json();
}

export async function fetchStats(): Promise<Stats> {
  const res = await fetch(`${API_URL}/stats`);
  if (!res.ok) throw new Error(`fetchStats: ${res.status}`);
  return res.json();
}

export async function fetchMonitoring(): Promise<{
  sources: MonitoringSource[];
}> {
  const res = await fetch(`${API_URL}/monitoring`);
  if (!res.ok) throw new Error(`fetchMonitoring: ${res.status}`);
  return res.json();
}
