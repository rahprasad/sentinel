"use client";

import { useEffect, useState } from "react";

const STEPS = [
  "Checking domain reputation...",
  "Walking the link in a sandbox...",
  "Writing your report...",
];

export default function InvestigatingProgress() {
  const [step, setStep] = useState(0);

  useEffect(() => {
    const id = setInterval(() => {
      setStep((s) => (s + 1) % STEPS.length);
    }, 2500);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="flex items-center gap-2 text-sm text-blue-400">
      <span className="h-2 w-2 rounded-full bg-blue-400 animate-pulse-dot" />
      <span>{STEPS[step]}</span>
    </div>
  );
}
