"use client";

import { useEffect } from "react";
import { useIncident } from "@/lib/api";
import type { Incident } from "@/lib/types";
import { WhatTheySent } from "./WhatTheySent";
import { WhatTheyWanted } from "./WhatTheyWanted";
import { HowWeCaughtIt } from "./HowWeCaughtIt";
import { HowToSpotIt } from "./HowToSpotIt";

/**
 * Drop-in drawer Person A renders from the dashboard.
 *
 *   <IncidentDrawer incidentId={selectedId} onClose={() => setSelectedId(null)} />
 *
 * Self-contained: fetches its own data, owns its own scroll, polls while
 * `status === "investigating"` so the live demo animates correctly.
 */
export interface IncidentDrawerProps {
  incidentId: string | null;
  onClose?: () => void;
}

export function IncidentDrawer({ incidentId, onClose }: IncidentDrawerProps) {
  const open = Boolean(incidentId);
  const { incident, error, loading } = useIncident(incidentId);

  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose?.();
    }
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  return (
    <div
      className={[
        "fixed inset-0 z-50 transition-opacity duration-200",
        open ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none",
      ].join(" ")}
      aria-hidden={!open}
    >
      <div
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        onClick={onClose}
      />
      <aside
        role="dialog"
        aria-modal="true"
        aria-label="Incident details"
        className={[
          "absolute right-0 top-0 h-full w-full max-w-2xl",
          "bg-slate-950 text-slate-100 shadow-2xl shadow-black/50",
          "border-l border-slate-800",
          "transform transition-transform duration-300 ease-out",
          open ? "translate-x-0" : "translate-x-full",
          "overflow-y-auto",
        ].join(" ")}
      >
        <DrawerHeader incident={incident} onClose={onClose} />
        <div className="px-8 py-6 space-y-10">
          {error ? <ErrorState error={error} /> : null}
          {!error && loading && !incident ? <LoadingState /> : null}
          {!error && incident ? <DrawerBody incident={incident} /> : null}
        </div>
      </aside>
    </div>
  );
}

function DrawerHeader({
  incident,
  onClose,
}: {
  incident: Incident | null;
  onClose?: () => void;
}) {
  const card = incident?.investigation;
  const investigating = incident?.status === "investigating" || incident?.status === "triaging";
  const safe = incident?.status === "safe";

  return (
    <header className="sticky top-0 z-10 bg-slate-950/95 backdrop-blur border-b border-slate-800 px-8 py-5">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-xs uppercase tracking-[0.18em] text-slate-500">
            {safe ? "Marked safe" : investigating ? "Investigating live" : "Caught it"}
          </p>
          <h2 className="mt-1 text-2xl font-semibold text-slate-50 truncate">
            {card?.scam_type ?? incident?.subject ?? "Investigating…"}
          </h2>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="rounded-md p-2 text-slate-400 hover:bg-slate-800 hover:text-slate-100 transition"
        >
          <span aria-hidden>✕</span>
        </button>
      </div>
      {incident?.estimated_loss_usd ? (
        <p className="mt-3 text-sm text-emerald-300">
          Saved you an estimated{" "}
          <span className="font-semibold text-emerald-200">
            ${incident.estimated_loss_usd.toLocaleString()}
          </span>
        </p>
      ) : null}
    </header>
  );
}

function DrawerBody({ incident }: { incident: Incident }) {
  const card = incident.investigation;
  if (!card) {
    return <PendingState incident={incident} />;
  }

  return (
    <>
      <WhatTheySent data={card.what_they_sent} source={incident.source} />
      <WhatTheyWanted
        what_they_wanted={card.what_they_wanted}
        harvested={card.evidence.harvested_fields ?? []}
      />
      <HowWeCaughtIt
        entries={card.how_we_caught_it}
        screenshots={incident.screenshots}
        evidence={card.evidence}
      />
      <HowToSpotIt rules={card.how_to_spot_it} />
    </>
  );
}

function PendingState({ incident }: { incident: Incident }) {
  const phases = [
    "Reading the message",
    "Checking domain reputation",
    "Walking the link in a sandbox",
    "Writing your report",
  ];
  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-400">
        Triage picked this up {timeAgo(incident.received_at)}. Investigation is
        running now — this view will update automatically.
      </p>
      <ul className="space-y-2">
        {phases.map((label) => (
          <li
            key={label}
            className="flex items-center gap-3 text-slate-300 text-sm"
          >
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
            {label}
          </li>
        ))}
      </ul>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="text-sm text-slate-400 animate-pulse">Loading incident…</div>
  );
}

function ErrorState({ error }: { error: Error }) {
  return (
    <div className="rounded-md border border-rose-800 bg-rose-950/40 px-4 py-3 text-sm text-rose-200">
      Couldn&apos;t load this incident: {error.message}
    </div>
  );
}

function timeAgo(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "just now";
  const secs = Math.max(1, Math.floor((Date.now() - then) / 1000));
  if (secs < 60) return `${secs}s ago`;
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`;
  return `${Math.floor(secs / 86400)}d ago`;
}
