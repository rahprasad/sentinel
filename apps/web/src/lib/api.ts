"use client";

import { useEffect, useState } from "react";
import type { Incident } from "./types";

export type { Incident } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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
  offset = 0,
): Promise<{ incidents: Incident[]; count: number }> {
  const res = await fetch(
    `${API_URL}/incidents?limit=${limit}&offset=${offset}`,
  );
  if (!res.ok) throw new Error(`fetchIncidents: ${res.status}`);
  return res.json();
}

export async function fetchIncident(id: string): Promise<Incident> {
  const res = await fetch(`${API_URL}/incidents/${id}`, { cache: "no-store" });
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

/**
 * Polls /incidents/{id} until status reaches a terminal state.
 *
 * While `status === "investigating"` (or "triaging") we keep ticking — that's
 * how the drawer animates from "we're working on it" to the final card during
 * the live demo. Polling stops as soon as the row reaches done/safe.
 */
export function useIncident(
  id: string | null,
  pollMs = 1500,
): { incident: Incident | null; error: Error | null; loading: boolean } {
  const [incident, setIncident] = useState<Incident | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState<boolean>(Boolean(id));

  useEffect(() => {
    if (!id) {
      setIncident(null);
      setError(null);
      setLoading(false);
      return;
    }

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    async function tick() {
      try {
        const result = await fetchIncident(id!);
        if (cancelled) return;
        setIncident(result);
        setLoading(false);
        if (result.status === "investigating" || result.status === "triaging") {
          timer = setTimeout(tick, pollMs);
        }
      } catch (err) {
        if (cancelled) return;
        setError(err as Error);
        setLoading(false);
      }
    }

    setLoading(true);
    setError(null);
    tick();

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [id, pollMs]);

  return { incident, error, loading };
}
