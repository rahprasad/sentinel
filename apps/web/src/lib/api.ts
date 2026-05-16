"use client";

import { useEffect, useState } from "react";
import type { Incident } from "./types";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function fetchIncident(id: string): Promise<Incident> {
  const res = await fetch(`${API_URL}/incidents/${id}`, {
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`incident ${id}: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

/**
 * Polls /incidents/{id} until status reaches a terminal state.
 *
 * While `status === "investigating"` we keep ticking — that's how the
 * drawer animates from "we're working on it" to the final card during
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
