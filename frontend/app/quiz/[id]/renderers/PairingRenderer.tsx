"use client";

import { useEffect, useRef, useState } from "react";
import type { Pairing } from "@/lib/problems";
import InlineText from "../InlineText";

function ChevronDown({ className = "" }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <polyline points="6 8 10 12 14 8" />
    </svg>
  );
}

function CustomSelect({
  value,
  onChange,
  options,
  disabled,
}: {
  value: string | undefined;
  onChange: (v: string) => void;
  options: string[];
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div ref={ref} className="relative flex-1 min-w-0">
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between gap-2 border border-border rounded-md px-3 py-2 text-base bg-card cursor-pointer hover:bg-card-hover text-left disabled:cursor-default disabled:opacity-60"
      >
        <span className="truncate text-fg">
          {value ? <InlineText text={value} /> : "Choose…"}
        </span>
        <ChevronDown
          className={`w-4 h-4 text-fg-subtle shrink-0 transition-transform ${
            open ? "rotate-180" : ""
          }`}
        />
      </button>
      {open && (
        <div className="absolute z-20 left-0 right-0 top-full mt-1 max-h-64 overflow-y-auto bg-card border border-border rounded-md shadow-lg py-1">
          {options.map((opt) => {
            const isCurrent = opt === value;
            return (
              <button
                key={opt}
                type="button"
                onClick={() => {
                  onChange(opt);
                  setOpen(false);
                }}
                className={`w-full text-left px-3 py-2 text-base cursor-pointer transition-colors ${
                  isCurrent
                    ? "bg-info-bg text-info-fg"
                    : "text-fg hover:bg-muted"
                }`}
              >
                <InlineText text={opt} />
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default function PairingRenderer({
  problem,
  rightShuffled,
  selected,
  onSubmit,
}: {
  problem: Pairing;
  rightShuffled: string[];
  selected: [string, string][] | undefined;
  onSubmit: (pairs: [string, string][]) => void;
}) {
  const submitted = selected !== undefined;
  const uniquePairs: [string, string][] = [];
  const seenLefts = new Set<string>();
  for (const [l, r] of problem.pairs) {
    if (seenLefts.has(l)) continue;
    seenLefts.add(l);
    uniquePairs.push([l, r]);
  }
  const lefts = uniquePairs.map(([l]) => l);
  const correctMap = new Map(uniquePairs);

  const [draft, setDraft] = useState<Record<string, string>>({});
  const displayMap: Record<string, string> = submitted
    ? Object.fromEntries(selected)
    : draft;

  const setRight = (left: string, right: string) => {
    if (submitted) return;
    setDraft((prev) => ({ ...prev, [left]: right }));
  };

  const allFilled = lefts.every((l) => draft[l]);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-2">
        {lefts.map((left, i) => {
          const userRight = displayMap[left];
          const correctRight = correctMap.get(left);
          const isCorrect = userRight === correctRight;

          let cls = "border-border bg-card text-fg";
          if (submitted) {
            cls = isCorrect
              ? "border-success-border bg-success-bg text-success-fg"
              : "border-danger-border bg-danger-bg text-danger-fg";
          }

          return (
            <div
              key={`${left}-${i}`}
              className={`flex items-center gap-3 text-base border rounded-lg px-4 py-3 min-h-[3.5rem] ${cls}`}
            >
              <span className="flex-1 min-w-0">
                <InlineText text={left} />
              </span>
              <span className="text-fg-faint select-none shrink-0" aria-hidden>
                →
              </span>
              {submitted ? (
                <span className="flex-1 min-w-0">
                  <span className="block">
                    <InlineText text={userRight ?? "—"} />
                  </span>
                  {!isCorrect && correctRight && (
                    <span className="block text-xs font-mono text-success-fg mt-1">
                      correct: <InlineText text={correctRight} />
                    </span>
                  )}
                </span>
              ) : (
                <CustomSelect
                  value={draft[left]}
                  onChange={(r) => setRight(left, r)}
                  options={rightShuffled}
                />
              )}
            </div>
          );
        })}
      </div>
      {!submitted && (
        <button
          type="button"
          onClick={() =>
            onSubmit(lefts.map((l) => [l, draft[l] ?? ""] as [string, string]))
          }
          disabled={!allFilled}
          className="self-start mt-1 px-3 py-1.5 rounded-md bg-primary text-white text-sm font-medium cursor-pointer transition-colors disabled:bg-muted disabled:text-fg-subtle disabled:cursor-default"
        >
          Submit
        </button>
      )}
    </div>
  );
}
