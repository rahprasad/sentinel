"use client";

/**
 * Screenshot drop zone — currently disabled as a "Coming soon" placeholder.
 * When the screenshot stretch goal is implemented, this component will be
 * enabled to accept image uploads and POST them to /ingest/screenshot.
 */
export default function ScreenshotDropZone() {
  return (
    <div className="rounded-xl border border-dashed border-[var(--card-border)] bg-[var(--card)] p-5 opacity-50">
      <div className="flex items-center justify-center gap-2 text-sm text-[var(--muted)]">
        <svg
          className="h-5 w-5"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1.5}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159M12 12.75l1.5-1.5m5.25 4.5H5.25a1.5 1.5 0 01-1.5-1.5V6.75a1.5 1.5 0 011.5-1.5h13.5a1.5 1.5 0 011.5 1.5v7.5a1.5 1.5 0 01-1.5 1.5z"
          />
        </svg>
        <span>Drop screenshot to scan</span>
        <span className="text-xs border border-[var(--card-border)] rounded px-1.5 py-0.5 ml-1">
          Coming soon
        </span>
      </div>
    </div>
  );
}
