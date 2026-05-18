"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import type { Highlight } from "@/lib/problems";

export default function HighlightRenderer({
  problem,
  repoId,
  selected,
  onSubmit,
}: {
  problem: Highlight;
  repoId: string;
  selected: number[] | undefined;
  onSubmit: (lines: number[]) => void;
}) {
  const router = useRouter();
  const submitted = selected !== undefined;
  const [draft, setDraft] = useState<Set<number>>(new Set());
  const [dragAnchor, setDragAnchor] = useState<number | null>(null);
  const [dragCurrent, setDragCurrent] = useState<number | null>(null);

  const snippet = problem.snippet;

  const dragMode: "add" | "remove" | null =
    dragAnchor === null ? null : draft.has(dragAnchor) ? "remove" : "add";

  const display = useMemo<Set<number>>(() => {
    if (submitted) return new Set(selected);
    if (dragAnchor === null || dragCurrent === null) return draft;
    const lo = Math.min(dragAnchor, dragCurrent);
    const hi = Math.max(dragAnchor, dragCurrent);
    const next = new Set(draft);
    for (let i = lo; i <= hi; i++) {
      if (dragMode === "add") next.add(i);
      else next.delete(i);
    }
    return next;
  }, [submitted, selected, draft, dragAnchor, dragCurrent, dragMode]);

  useEffect(() => {
    if (dragAnchor === null) return;
    const onUp = () => {
      setDraft((prev) => {
        const anchor = dragAnchor;
        const current = dragCurrent ?? dragAnchor;
        const lo = Math.min(anchor, current);
        const hi = Math.max(anchor, current);
        const next = new Set(prev);
        const mode = prev.has(anchor) ? "remove" : "add";
        for (let i = lo; i <= hi; i++) {
          if (mode === "add") next.add(i);
          else next.delete(i);
        }
        return next;
      });
      setDragAnchor(null);
      setDragCurrent(null);
    };
    window.addEventListener("mouseup", onUp);
    return () => window.removeEventListener("mouseup", onUp);
  }, [dragAnchor, dragCurrent]);

  if (!snippet || snippet.error) {
    return (
      <div className="text-sm text-danger font-mono">
        Snippet unavailable: {snippet?.error ?? "no snippet data"}
      </div>
    );
  }

  const correctSet = new Set(snippet.correctLines);

  const openSnippet = () => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams({
      file: snippet.path,
      line: `${snippet.startLine}-${snippet.endLine}`,
    });
    const url = new URL(window.location.href);
    const sameFile = url.searchParams.get("file") === snippet.path;
    const sameLine =
      url.searchParams.get("line") === `${snippet.startLine}-${snippet.endLine}`;
    if (sameFile && sameLine) {
      window.dispatchEvent(
        new CustomEvent("citation-flash", {
          detail: {
            path: snippet.path,
            line: `${snippet.startLine}-${snippet.endLine}`,
          },
        }),
      );
    } else {
      router.push(`/quiz/${repoId}?${params.toString()}`, { scroll: false });
    }
  };

  const lineNumWidth = String(snippet.endLine).length;
  const isDragging = dragAnchor !== null;

  return (
    <div className="flex flex-col gap-3">
      <div className="rounded-md border border-border overflow-hidden">
        <button
          type="button"
          onClick={openSnippet}
          title="Open in viewer"
          className="w-full flex items-center justify-between gap-2 px-3 py-1.5 bg-surface border-b border-border hover:bg-muted text-fg-muted cursor-pointer transition-colors font-mono text-xs text-left"
        >
          <span className="truncate">
            {snippet.path}
            <span className="text-fg-subtle">
              :{snippet.startLine}-{snippet.endLine}
            </span>
          </span>
          <svg
            className="w-3.5 h-3.5 text-fg-subtle shrink-0"
            viewBox="0 0 16 16"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <path d="M6 3h7v7" />
            <path d="M13 3 4 12" />
          </svg>
        </button>

        <div className="shiki scroll-on-hover overflow-x-auto font-mono text-sm bg-surface">
          <div className={`min-w-max ${isDragging ? "select-none" : ""}`}>
            {snippet.lines.map((lineHtml, i) => {
              const absLine = snippet.startLine + i;
              const isSelected = display.has(absLine);
              const isCorrect = correctSet.has(absLine);

              let overlay = "";
              if (submitted) {
                if (isCorrect && isSelected) overlay = "bg-hl-correct";
                else if (isCorrect) overlay = "bg-hl-hint";
                else if (isSelected) overlay = "bg-hl-incorrect";
              } else if (isSelected) {
                overlay = "bg-hl-selected";
              }

              return (
                <div
                  key={absLine}
                  onMouseDown={(e) => {
                    if (submitted) return;
                    e.preventDefault();
                    setDragAnchor(absLine);
                    setDragCurrent(absLine);
                  }}
                  onMouseEnter={() => {
                    if (submitted || dragAnchor === null) return;
                    setDragCurrent(absLine);
                  }}
                  className={`flex items-start ${overlay} ${
                    submitted
                      ? "cursor-default"
                      : isSelected
                        ? "cursor-pointer hover:bg-hl-selected-hover"
                        : "cursor-pointer hover:bg-hl-hover"
                  }`}
                >
                  <span
                    className="text-fg-faint select-none text-right shrink-0 pl-3 pr-3"
                    style={{ width: `${lineNumWidth + 1}ch` }}
                  >
                    {absLine}
                  </span>
                  <span
                    className="whitespace-pre flex-1 pr-3"
                    dangerouslySetInnerHTML={{ __html: lineHtml || "&nbsp;" }}
                  />
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {!submitted && (
        <button
          type="button"
          onClick={() =>
            onSubmit(Array.from(draft).sort((a, b) => a - b))
          }
          className="self-start mt-1 px-3 py-1.5 rounded-md bg-primary text-white text-sm font-medium cursor-pointer"
        >
          Submit
        </button>
      )}
    </div>
  );
}
