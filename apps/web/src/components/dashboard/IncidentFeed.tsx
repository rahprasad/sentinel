"use client";

import { usePolling } from "@/hooks/use-polling";
import { fetchIncidents, type Incident } from "@/lib/api";
import IncidentRow from "./IncidentRow";

const POLL_MS = Number(process.env.NEXT_PUBLIC_POLL_INCIDENTS_MS || 2000);

export default function IncidentFeed({
  onSelect,
}: {
  onSelect?: (id: string) => void;
}) {
  const { data } = usePolling(() => fetchIncidents(50), POLL_MS);

  const incidents: Incident[] = data?.incidents ?? [];

  return (
    <div className="rounded-xl border border-[var(--card-border)] bg-[var(--card)] p-5">
      <h2 className="text-sm font-semibold text-[var(--muted)] uppercase tracking-wider mb-3">
        Recent Activity
      </h2>
      <div className="space-y-1 max-h-[400px] overflow-y-auto">
        {incidents.length === 0 && (
          <p className="text-sm text-[var(--muted)] py-4 text-center">
            No incidents yet. Send a scam email to get started.
          </p>
        )}
        {incidents.map((incident) => (
          <IncidentRow
            key={incident.id}
            incident={incident}
            onClick={onSelect}
          />
        ))}
      </div>
    </div>
  );
}
