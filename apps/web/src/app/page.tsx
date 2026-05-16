import DashboardClient from "./DashboardClient";

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

      <DashboardClient />

      {/* Footer */}
      <footer className="border-t border-[var(--card-border)] px-6 py-4 mt-8">
        <div className="max-w-5xl mx-auto text-center text-xs text-[var(--muted)]">
          ScamShield — Always-on scam protection for your inbox and beyond.
        </div>
      </footer>
    </div>
  );
}
