"use client";

import { useEffect, useState } from "react";

interface Props {
  screenshots: string[];
  finalUrl: string | null;
}

/**
 * The visceral demo moment: a thumbnail strip of the sandbox walk plus a
 * lightbox-style expanded view. Captions are derived from step ordering
 * — the synthesizer's "how we caught it" text already does the prose.
 */
export function SandboxReplay({ screenshots, finalUrl }: Props) {
  const [activeIdx, setActiveIdx] = useState<number | null>(null);

  useEffect(() => {
    if (activeIdx === null) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setActiveIdx(null);
      if (e.key === "ArrowRight")
        setActiveIdx((i) =>
          i === null ? null : Math.min(i + 1, screenshots.length - 1),
        );
      if (e.key === "ArrowLeft")
        setActiveIdx((i) => (i === null ? null : Math.max(i - 1, 0)));
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [activeIdx, screenshots.length]);

  if (screenshots.length === 0) return null;

  return (
    <figure>
      <figcaption className="mb-2 text-[11px] uppercase tracking-wider text-slate-500">
        Sandbox replay · {screenshots.length} step{screenshots.length > 1 ? "s" : ""}
        {finalUrl ? (
          <span className="ml-2 normal-case tracking-normal text-slate-400">
            → {hostnameOf(finalUrl)}
          </span>
        ) : null}
      </figcaption>
      <ol className="flex gap-3 overflow-x-auto pb-2 -mx-1 px-1 snap-x snap-mandatory">
        {screenshots.map((url, i) => (
          <li
            key={url}
            className="snap-start shrink-0"
          >
            <button
              type="button"
              onClick={() => setActiveIdx(i)}
              className={[
                "group relative block rounded-lg overflow-hidden",
                "ring-1 ring-slate-800 hover:ring-slate-600 transition",
                "focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400",
              ].join(" ")}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={url}
                alt={`Sandbox step ${i + 1}`}
                className="h-44 w-72 object-cover object-top bg-slate-800"
                loading="lazy"
              />
              <span className="absolute left-2 top-2 rounded-md bg-black/70 px-2 py-0.5 text-[10px] font-medium text-slate-100">
                Step {i + 1}
              </span>
            </button>
          </li>
        ))}
      </ol>

      {activeIdx !== null ? (
        <Lightbox
          screenshots={screenshots}
          index={activeIdx}
          onClose={() => setActiveIdx(null)}
          onPrev={() => setActiveIdx((i) => (i === null ? null : Math.max(i - 1, 0)))}
          onNext={() =>
            setActiveIdx((i) =>
              i === null ? null : Math.min(i + 1, screenshots.length - 1),
            )
          }
        />
      ) : null}
    </figure>
  );
}

function Lightbox({
  screenshots,
  index,
  onClose,
  onPrev,
  onNext,
}: {
  screenshots: string[];
  index: number;
  onClose: () => void;
  onPrev: () => void;
  onNext: () => void;
}) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={`Sandbox step ${index + 1}`}
      className="fixed inset-0 z-[60] flex items-center justify-center bg-black/90 p-6"
      onClick={onClose}
    >
      <div
        className="relative max-h-full max-w-5xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={screenshots[index]}
          alt={`Sandbox step ${index + 1}`}
          className="max-h-[85vh] w-auto rounded-lg shadow-2xl"
        />
        <div className="mt-3 flex items-center justify-between text-sm text-slate-300">
          <span>
            Step {index + 1} of {screenshots.length}
          </span>
          <div className="flex gap-2">
            <NavBtn onClick={onPrev} disabled={index === 0} label="←" />
            <NavBtn
              onClick={onNext}
              disabled={index === screenshots.length - 1}
              label="→"
            />
            <NavBtn onClick={onClose} label="Close" />
          </div>
        </div>
      </div>
    </div>
  );
}

function NavBtn({
  onClick,
  disabled,
  label,
}: {
  onClick: () => void;
  disabled?: boolean;
  label: string;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={[
        "rounded-md border px-3 py-1.5 text-sm transition",
        disabled
          ? "border-slate-800 text-slate-600"
          : "border-slate-700 text-slate-200 hover:bg-slate-800",
      ].join(" ")}
    >
      {label}
    </button>
  );
}

function hostnameOf(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return url;
  }
}
