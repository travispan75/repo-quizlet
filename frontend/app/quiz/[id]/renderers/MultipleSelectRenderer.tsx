"use client";

import { useState } from "react";
import type { MultipleSelect } from "@/lib/problems";
import InlineText from "../InlineText";

export default function MultipleSelectRenderer({
  problem,
  options,
  selected,
  onSubmit,
}: {
  problem: MultipleSelect;
  options: string[];
  selected: string[] | undefined;
  onSubmit: (choices: string[]) => void;
}) {
  const submitted = selected !== undefined;
  const correctSet = new Set(problem.correct);
  const [draft, setDraft] = useState<Set<string>>(new Set());
  const display = submitted ? new Set(selected) : draft;

  const toggle = (opt: string) => {
    if (submitted) return;
    setDraft((prev) => {
      const next = new Set(prev);
      if (next.has(opt)) next.delete(opt);
      else next.add(opt);
      return next;
    });
  };

  return (
    <div className="@container flex flex-col gap-3">
      <div className="grid grid-cols-1 @md:grid-cols-2 gap-3">
        {options.map((opt) => {
          const isSelected = display.has(opt);
          const isCorrect = correctSet.has(opt);

          let boxCls = "border-border bg-card text-fg hover:bg-card-hover";
          if (submitted) {
            if (isCorrect && isSelected)
              boxCls = "border-success-border bg-success-bg text-success-fg";
            else if (isCorrect)
              boxCls = "border-success-border bg-card text-success-fg";
            else if (isSelected)
              boxCls = "border-danger-border bg-danger-bg text-danger-fg";
            else boxCls = "border-border bg-card text-fg";
          } else if (isSelected) {
            boxCls = "border-selection-border bg-selection-bg";
          }

          let checkboxCls: string;
          if (isSelected) {
            checkboxCls = submitted
              ? isCorrect
                ? "bg-success border-success"
                : "bg-danger border-danger"
              : "bg-primary border-primary";
          } else {
            checkboxCls =
              submitted && isCorrect
                ? "bg-card border-success"
                : "bg-card border-border-hover";
          }

          return (
            <button
              key={opt}
              type="button"
              disabled={submitted}
              onClick={() => toggle(opt)}
              className={`flex items-center gap-3 text-left text-base border rounded-lg px-4 py-3 min-h-[3.5rem] transition-colors disabled:cursor-default cursor-pointer ${boxCls}`}
            >
              <span
                className={`w-5 h-5 rounded border-2 flex items-center justify-center shrink-0 transition-colors ${checkboxCls}`}
              >
                {isSelected && (
                  <svg
                    className="w-3.5 h-3.5 text-white"
                    viewBox="0 0 20 20"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="3"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <polyline points="5 10 9 14 15 6" />
                  </svg>
                )}
              </span>
              <span className="block flex-1 min-w-0">
                <InlineText text={opt} />
              </span>
            </button>
          );
        })}
      </div>
      {!submitted && (
        <button
          type="button"
          onClick={() => onSubmit(Array.from(draft))}
          disabled={draft.size === 0}
          className="self-start mt-1 px-3 py-1.5 rounded-md bg-primary text-white text-sm font-medium cursor-pointer transition-colors disabled:bg-muted disabled:text-fg-subtle disabled:cursor-default"
        >
          Submit
        </button>
      )}
    </div>
  );
}
