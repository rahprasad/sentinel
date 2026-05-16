"use client";

import type { Incident } from "@/lib/api";

const SCAM_ICONS: Record<string, string> = {
  phishing: "\uD83C\uDFF4",
  romance: "\uD83E\uDDF4",
  delivery: "\uD83D\uDE9A",
  refund: "\uD83D\uDCB8",
  crypto: "\uD83E\uDE99",
  support: "\uD83D\uDCDE",
  other: "\u26A0\uFE0F",
  none: "\u2705",
};

function timeAgo(isoDate: string): string {
  const seconds = Math.floor(
    (Date.now() - new Date(isoDate).getTime()) / 1000
  );
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h`;
  const days = Math.floor(hours / 24);
  return `${days}d`;
}

function StatusPill({ status }: { status: Incident["status"] }) {
  const styles: Record<string, string> = {
    triaging:
      "bg-yellow-500/10 text-yellow-400 border-yellow-500/20",
    investigating:
      "bg-blue-500/10 text-blue-400 border-blue-500/20",
    done: "bg-green-500/10 text-green-400 border-green-500/20",
    safe: "bg-gray-500/10 text-gray-400 border-gray-500/20",
  };

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${styles[status] || styles.safe}`}
    >
      {status}
    </span>
  );
}

export default function IncidentRow({
  incident,
  onClick,
}: {
  incident: Incident;
  onClick?: (id: string) => void;
}) {
  const scamType = incident.triage?.scam_type || "none";
  const icon = SCAM_ICONS[scamType] || SCAM_ICONS.other;
  const oneLiner =
    incident.subject || incident.body?.slice(0, 80) || "No content";

  return (
    <button
      type="button"
      onClick={() => onClick?.(incident.id)}
      className="w-full min-w-0 flex items-center gap-3 px-4 py-3 rounded-lg hover:bg-white/5 transition-colors text-left animate-slide-in"
    >
      <span className="text-xl flex-shrink-0">{icon}</span>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate">{oneLiner}</p>
        <p className="text-xs text-[var(--muted)] truncate">
          {incident.sender}
        </p>
      </div>
      <StatusPill status={incident.status} />
      <span className="text-xs text-[var(--muted)] flex-shrink-0 w-8 text-right">
        {timeAgo(incident.received_at)}
      </span>
    </button>
  );
}
