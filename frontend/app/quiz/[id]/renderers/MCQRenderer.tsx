"use client";

import { useState } from "react";
import type { MCQ } from "@/lib/problems";
import InlineText from "../InlineText";

export default function MCQRenderer({
  problem,
  options,
  selected,
  onSubmit,
}: {
  problem: MCQ;
  options: string[];
  selected: string | undefined;
  onSubmit: (choice: string) => void;
}) {
  const submitted = selected !== undefined;
  const [draft, setDraft] = useState<string | undefined>(undefined);
  const display = submitted ? selected : draft;

  return (
    <div className="@container flex flex-col gap-3">
      <div className="grid grid-cols-1 @md:grid-cols-2 gap-3">
        {options.map((opt) => {
          const isSelected = display === opt;
          const isCorrect = opt === problem.correct;

          let cls = "border-border bg-card text-fg hover:bg-card-hover";
          if (submitted) {
            if (isCorrect && isSelected)
              cls = "border-success-border bg-success-bg text-success-fg";
            else if (isCorrect)
              cls = "border-success-border bg-card text-success-fg";
            else if (isSelected)
              cls = "border-danger-border bg-danger-bg text-danger-fg";
            else cls = "border-border bg-card text-fg";
          } else if (isSelected) {
            cls = "border-selection-border bg-selection-bg";
          }

          return (
            <button
              key={opt}
              type="button"
              disabled={submitted}
              onClick={() => setDraft(opt)}
              className={`flex items-center text-left text-base border rounded-lg px-4 py-3 min-h-[3.5rem] transition-colors disabled:cursor-default cursor-pointer ${cls}`}
            >
              <span className="block w-full">
                <InlineText text={opt} />
              </span>
            </button>
          );
        })}
      </div>
      {!submitted && (
        <button
          type="button"
          onClick={() => draft !== undefined && onSubmit(draft)}
          disabled={draft === undefined}
          className="self-start mt-1 px-3 py-1.5 rounded-md bg-primary text-white text-sm font-medium cursor-pointer transition-colors disabled:bg-muted disabled:text-fg-subtle disabled:cursor-default"
        >
          Submit
        </button>
      )}
    </div>
  );
}
