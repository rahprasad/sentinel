import MonitoringStatus from "@/components/dashboard/MonitoringStatus";
import HeroStats from "@/components/dashboard/HeroStats";
import IncidentFeed from "@/components/dashboard/IncidentFeed";
import TrendingStrip from "@/components/dashboard/TrendingStrip";
import ScreenshotDropZone from "@/components/dashboard/ScreenshotDropZone";

export default function Home() {
  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="border-b border-[var(--card-border)] px-6 py-4">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-xl font-bold tracking-tight">
              ScamShield
            </span>
            <span className="text-xs text-[var(--muted)] border border-[var(--card-border)] rounded px-2 py-0.5">
              Sentinel
            </span>
          </div>
          <div className="flex items-center gap-4 text-[var(--muted)]">
            <span className="text-sm">v0.1.0</span>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-5xl mx-auto px-6 py-6 space-y-6">
        {/* Row 1: Monitoring + Screenshot drop zone */}
        <div className="grid grid-cols-1 md:grid-cols-[1fr_1fr] gap-4">
          <MonitoringStatus />
          <ScreenshotDropZone />
        </div>

        {/* Row 2: Hero stats */}
        <HeroStats />

        {/* Row 3: Incident feed + Trending */}
        <div className="grid grid-cols-1 md:grid-cols-[2fr_1fr] gap-4">
          <IncidentFeed />
          <TrendingStrip />
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-[var(--card-border)] px-6 py-4 mt-8">
        <div className="max-w-5xl mx-auto text-center text-xs text-[var(--muted)]">
          ScamShield — Always-on scam protection for your inbox and beyond.
        </div>
      </footer>
    </div>
  );
}
