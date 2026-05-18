"use client";

import { useState } from "react";
import type { TF } from "@/lib/problems";

export default function TFRenderer({
  problem,
  selected,
  onSubmit,
}: {
  problem: TF;
  selected: boolean | undefined;
  onSubmit: (choice: boolean) => void;
}) {
  const submitted = selected !== undefined;
  const [draft, setDraft] = useState<boolean | undefined>(undefined);
  const display = submitted ? selected : draft;

  return (
    <div className="@container flex flex-col gap-3">
      <div className="grid grid-cols-1 @md:grid-cols-2 gap-3">
        {[true, false].map((val) => {
          const isSelected = val === display;
          const isCorrect = val === problem.is_true;

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
              key={String(val)}
              type="button"
              disabled={submitted}
              onClick={() => setDraft(val)}
              className={`flex items-center justify-center text-base border rounded-lg px-4 py-3 min-h-[3.5rem] transition-colors disabled:cursor-default cursor-pointer ${cls}`}
            >
              {val ? "True" : "False"}
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
