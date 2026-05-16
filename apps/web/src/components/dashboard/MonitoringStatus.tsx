"use client";

import { usePolling } from "@/hooks/use-polling";
import { fetchMonitoring, type MonitoringSource } from "@/lib/api";

const POLL_MS = Number(process.env.NEXT_PUBLIC_POLL_MONITORING_MS || 3000);

function timeSince(isoDate: string | null): string {
  if (!isoDate) return "never";
  const seconds = Math.floor(
    (Date.now() - new Date(isoDate).getTime()) / 1000
  );
  if (seconds < 5) return "just now";
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  return `${Math.floor(minutes / 60)}h ago`;
}

function sourceLabel(source: string): string {
  const labels: Record<string, string> = {
    email_imap: "Inbox (IMAP)",
    email_webhook: "Inbox (Webhook)",
    screenshot: "Screenshot",
  };
  return labels[source] || source;
}

function StateIndicator({ state }: { state: MonitoringSource["state"] }) {
  if (state === "active") {
    return (
      <span className="inline-flex items-center gap-1.5">
        <span className="h-2 w-2 rounded-full bg-[var(--success)] animate-pulse-dot" />
        <span className="text-[var(--success)] text-sm font-medium">
          Active
        </span>
      </span>
    );
  }
  if (state === "error") {
    return (
      <span className="inline-flex items-center gap-1.5">
        <span className="h-2 w-2 rounded-full bg-[var(--danger)]" />
        <span className="text-[var(--danger)] text-sm font-medium">Error</span>
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="h-2 w-2 rounded-full bg-[var(--warning)]" />
      <span className="text-[var(--warning)] text-sm font-medium">
        Paused
      </span>
    </span>
  );
}

export default function MonitoringStatus() {
  const { data } = usePolling(() => fetchMonitoring(), POLL_MS);

  const sources = data?.sources || [];

  return (
    <div className="rounded-xl border border-[var(--card-border)] bg-[var(--card)] p-5">
      <h2 className="text-sm font-semibold text-[var(--muted)] uppercase tracking-wider mb-3">
        Monitoring email
      </h2>
      <div className="space-y-3">
        {sources.map((src) => (
          <div
            key={src.source}
            className="flex items-center justify-between"
          >
            <div className="flex items-center gap-3">
              <StateIndicator state={src.state} />
              <span className="text-sm">
                {sourceLabel(src.source)}
              </span>
            </div>
            <div className="text-right text-xs text-[var(--muted)]">
              <div>
                Last check:{" "}
                {src.state === "active"
                  ? timeSince(src.last_check)
                  : "—"}
              </div>
              {src.items_scanned_total > 0 && (
                <div>{src.items_scanned_total} scanned</div>
              )}
            </div>
          </div>
        ))}
        {sources.length === 0 && (
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="inline-flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-[var(--success)] animate-pulse-dot" />
                <span className="text-[var(--success)] text-sm font-medium">
                  Active
                </span>
              </span>
              <span className="text-sm">Inbox (IMAP)</span>
            </div>
            <div className="text-right text-xs text-[var(--muted)]">
              <div>Watching for new messages…</div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
