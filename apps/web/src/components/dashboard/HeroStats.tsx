"use client";

import { usePolling } from "@/hooks/use-polling";
import { fetchStats } from "@/lib/api";

const POLL_MS = 5000;

export default function HeroStats() {
  const { data } = usePolling(() => fetchStats(), POLL_MS);

  const blocked = data?.blocked_count ?? 0;
  const scanned = data?.scanned_today ?? 0;

  return (
    <div className="grid grid-cols-2 gap-4">
      <div className="rounded-xl border border-[var(--card-border)] bg-[var(--card)] p-5 text-center">
        <p className="text-3xl font-bold text-[var(--accent)]">{blocked}</p>
        <p className="text-sm text-[var(--muted)] mt-1">Scams Blocked</p>
      </div>
      <div className="rounded-xl border border-[var(--card-border)] bg-[var(--card)] p-5 text-center">
        <p className="text-3xl font-bold text-[var(--foreground)]">
          {scanned}
        </p>
        <p className="text-sm text-[var(--muted)] mt-1">Messages Scanned</p>
      </div>
    </div>
  );
}
