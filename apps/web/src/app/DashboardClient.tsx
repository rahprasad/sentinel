"use client";

import { useState } from "react";
import MonitoringStatus from "@/components/dashboard/MonitoringStatus";
import HeroStats from "@/components/dashboard/HeroStats";
import IncidentFeed from "@/components/dashboard/IncidentFeed";
import TrendingStrip from "@/components/dashboard/TrendingStrip";
import ScreenshotDropZone from "@/components/dashboard/ScreenshotDropZone";
import { IncidentDrawer } from "@/components/drawer";

export default function DashboardClient() {
  const [selectedIncidentId, setSelectedIncidentId] = useState<string | null>(null);

  return (
    <>
      <main className="max-w-5xl mx-auto px-6 py-6 space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-4">
          <div className="min-w-0">
            <MonitoringStatus />
          </div>
          <div className="min-w-0">
            <ScreenshotDropZone />
          </div>
        </div>

        <HeroStats />

        <div className="grid grid-cols-1 md:grid-cols-[minmax(0,2fr)_minmax(0,1fr)] gap-4">
          <div className="min-w-0">
            <IncidentFeed onSelect={setSelectedIncidentId} />
          </div>
          <div className="min-w-0">
            <TrendingStrip />
          </div>
        </div>
      </main>

      <IncidentDrawer
        incidentId={selectedIncidentId}
        onClose={() => setSelectedIncidentId(null)}
      />
    </>
  );
}
