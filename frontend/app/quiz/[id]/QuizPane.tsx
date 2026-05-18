"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type { Problem } from "@/lib/problems";
import { backend } from "@/lib/backend";
import MCQRenderer from "./renderers/MCQRenderer";
import TFRenderer from "./renderers/TFRenderer";
import MultipleSelectRenderer from "./renderers/MultipleSelectRenderer";
import OrderRenderer from "./renderers/OrderRenderer";
import PairingRenderer from "./renderers/PairingRenderer";
import HighlightRenderer from "./renderers/HighlightRenderer";
import InlineText from "./InlineText";

const COMPLETION_ANIM_MS = 1500;

function useCountUp(target: number, durationMs: number): number {
  const [value, setValue] = useState(0);
  useEffect(() => {
    if (target <= 0) {
      setValue(0);
      return;
    }
    let raf = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / durationMs);
      const eased = 1 - Math.pow(1 - t, 3);
      setValue(Math.round(eased * target));
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, durationMs]);
  return value;
}

function ConceptRow({
  title,
  correct,
  total,
  color,
}: {
  title: string;
  correct: number;
  total: number;
  color: string;
}) {
  const animatedCorrect = useCountUp(correct, COMPLETION_ANIM_MS);
  const ratio = total > 0 ? correct / total : 0;
  const [barWidth, setBarWidth] = useState(0);
  useEffect(() => {
    const raf = requestAnimationFrame(() => setBarWidth(ratio * 100));
    return () => cancelAnimationFrame(raf);
  }, [ratio]);

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-baseline justify-between gap-3">
        <div className="text-sm text-fg truncate">{title}</div>
        <div className="text-xs font-mono text-fg-muted tabular-nums shrink-0">
          {animatedCorrect} / {total}
        </div>
      </div>
      <div className="h-2 w-full bg-muted rounded-full overflow-hidden">
        <div
          className={`h-full ${color}`}
          style={{
            width: `${barWidth}%`,
            transition: `width ${COMPLETION_ANIM_MS}ms ease-out`,
          }}
        />
      </div>
    </div>
  );
}

type UserAnswer =
  | { kind: "MCQ"; selected: string }
  | { kind: "TF"; selected: boolean }
  | { kind: "MultipleSelect"; selected: string[] }
  | { kind: "Order"; ordered: string[] }
  | { kind: "Pairing"; pairs: [string, string][] }
  | { kind: "Highlight"; selectedLineIndices: number[] };

type InProgress = {
  status: "in_progress";
  startedAt: number;
  order: string[];
  currentIndex: number;
  answers: Record<string, UserAnswer>;
  optionOrders: Record<string, string[]>;
};

type Completed = {
  status: "completed";
  startedAt: number;
  finishedAt: number;
  order: string[];
  answers: Record<string, UserAnswer>;
  optionOrders: Record<string, string[]>;
};

type QuizState = { status: "not_started" } | InProgress | Completed;

function storageKey(repoId: string) {
  return `quiz:${repoId}`;
}

function shuffle<T>(arr: T[]): T[] {
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

function isValidState(x: unknown): x is QuizState {
  if (!x || typeof x !== "object") return false;
  const s = x as Record<string, unknown>;

  if (s.status === "not_started") return true;

  if (s.status === "in_progress") {
    return (
      Array.isArray(s.order) &&
      typeof s.currentIndex === "number" &&
      s.answers != null &&
      s.optionOrders != null
    );
  }

  if (s.status === "completed") {
    return (
      Array.isArray(s.order) &&
      s.answers != null &&
      s.optionOrders != null
    );
  }

  return false;
}

function parseCitation(c: string): { path: string; line: string | null } {
  const idx = c.lastIndexOf(":");
  if (idx === -1) return { path: c, line: null };
  const right = c.slice(idx + 1);
  if (/^\d+(-\d+)?$/.test(right)) {
    return { path: c.slice(0, idx), line: right };
  }
  return { path: c, line: null };
}

function arraysEqualSorted<T>(a: T[], b: T[]): boolean {
  if (a.length !== b.length) return false;
  const sa = [...a].sort();
  const sb = [...b].sort();
  return sa.every((v, i) => v === sb[i]);
}

type ProgressData =
  | { status: "idle" }
  | {
      status: "running";
      pipeline: string;
      stage_label: string;
      stage_index: number;
      stage_total: number;
      sub_done: number;
      sub_total: number;
      repo_updated?: boolean;
      updated_at: number;
    }
  | { status: "done"; updated_at: number }
  | { status: "failed"; error?: string; updated_at: number };

function useProgress(repoId: string, enabled: boolean): ProgressData | null {
  const [data, setData] = useState<ProgressData | null>(null);
  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    const tick = async () => {
      try {
        const next = (await backend.getProgress(repoId)) as ProgressData;
        if (!cancelled) setData(next);
      } catch {}
    };
    tick();
    const interval = setInterval(tick, 1500);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [repoId, enabled]);
  return data;
}

function computeProgressFraction(p: {
  stage_index: number;
  stage_total: number;
  sub_done: number;
  sub_total: number;
}): number {
  if (p.stage_total <= 0) return 0;
  const completedStages = Math.max(0, p.stage_index - 1) / p.stage_total;
  const within =
    p.sub_total > 0 ? p.sub_done / p.sub_total / p.stage_total : 0;
  return Math.min(1, completedStages + within);
}

function isAnswerCorrect(problem: Problem, answer: UserAnswer): boolean {
  if (problem.kind === "MCQ" && answer.kind === "MCQ") {
    return answer.selected === problem.correct;
  }
  if (problem.kind === "TF" && answer.kind === "TF") {
    return answer.selected === problem.is_true;
  }
  if (problem.kind === "MultipleSelect" && answer.kind === "MultipleSelect") {
    return arraysEqualSorted(answer.selected, problem.correct);
  }
  if (problem.kind === "Order" && answer.kind === "Order") {
    return (
      answer.ordered.length === problem.correct_order.length &&
      answer.ordered.every((v, i) => v === problem.correct_order[i])
    );
  }
  if (problem.kind === "Pairing" && answer.kind === "Pairing") {
    const correctMap = new Map(problem.pairs);
    return (
      answer.pairs.length === problem.pairs.length &&
      answer.pairs.every(([l, r]) => correctMap.get(l) === r)
    );
  }
  if (problem.kind === "Highlight" && answer.kind === "Highlight") {
    return arraysEqualSorted(
      answer.selectedLineIndices,
      problem.snippet?.correctLines ?? [],
    );
  }
  return false;
}

export default function QuizPane({
  repoId,
  problems,
  topicTitles,
  error,
  dataLoading = false,
  onPipelineDone,
}: {
  repoId: string;
  problems: Problem[];
  topicTitles: Record<string, string>;
  error?: string;
  dataLoading?: boolean;
  onPipelineDone?: () => void;
}) {
  const router = useRouter();
  const [state, setState] = useState<QuizState | null>(null);
  const [navOpen, setNavOpen] = useState(false);
  const navTriggerRef = useRef<HTMLButtonElement>(null);
  const navPopoverRef = useRef<HTMLDivElement>(null);
  const lastProgressStatus = useRef<string | null>(null);

  const problemsById = useMemo(
    () => new Map(problems.map((p) => [p.problem_id, p])),
    [problems],
  );

  const progressEnabled = !dataLoading && problems.length === 0;
  const progress = useProgress(repoId, progressEnabled);

  useEffect(() => {
    if (!progress) return;
    if (
      progress.status === "done" &&
      lastProgressStatus.current !== "done"
    ) {
      lastProgressStatus.current = "done";
      onPipelineDone?.();
      return;
    }
    lastProgressStatus.current = progress.status;
  }, [progress, onPipelineDone]);

  useEffect(() => {
    if (!navOpen) return;
    const handler = (e: MouseEvent) => {
      const target = e.target as Node;
      if (
        navPopoverRef.current &&
        !navPopoverRef.current.contains(target) &&
        navTriggerRef.current &&
        !navTriggerRef.current.contains(target)
      ) {
        setNavOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [navOpen]);

  useEffect(() => {
    const raw = localStorage.getItem(storageKey(repoId));
    if (raw) {
      try {
        const parsed = JSON.parse(raw);
        if (isValidState(parsed)) {
          if (parsed.status === "not_started") {
            setState(parsed);
            return;
          }
          const allKnown = parsed.order.every((id: string) =>
            problemsById.has(id),
          );
          if (allKnown) {
            setState(parsed);
            return;
          }
        }
      } catch {}
    }
    setState({ status: "not_started" });
  }, [repoId, problemsById]);

  useEffect(() => {
    if (state === null) return;
    if (state.status === "not_started") {
      localStorage.removeItem(storageKey(repoId));
    } else {
      localStorage.setItem(storageKey(repoId), JSON.stringify(state));
    }
  }, [state, repoId]);

  if (error) {
    return (
      <div className="h-full flex items-center justify-center p-6 text-center text-danger">
        {error}
      </div>
    );
  }

  if (state === null) return null;

  if (state.status === "not_started") {
    const beginQuiz = () => {
      const order = shuffle(problems.map((p) => p.problem_id));
      const optionOrders: Record<string, string[]> = {};
      for (const p of problems) {
        if (p.kind === "MCQ") {
          optionOrders[p.problem_id] = shuffle([p.correct, ...p.distractors]);
        } else if (p.kind === "MultipleSelect") {
          optionOrders[p.problem_id] = shuffle([
            ...p.correct,
            ...p.distractors,
          ]);
        } else if (p.kind === "Order") {
          optionOrders[p.problem_id] = shuffle(p.correct_order);
        } else if (p.kind === "Pairing") {
          optionOrders[p.problem_id] = shuffle(p.pairs.map(([, r]) => r));
        }
      }
      setState({
        status: "in_progress",
        startedAt: Date.now(),
        order,
        currentIndex: 0,
        answers: {},
        optionOrders,
      });
    };

    if (progressEnabled && progress?.status === "running") {
      const fraction = computeProgressFraction(progress);
      return (
        <div className="h-full flex flex-col items-center justify-center gap-4 p-6">
          {progress.repo_updated && (
            <div className="text-xs text-info-fg bg-info-bg border border-info-border/40 rounded-md px-3 py-1.5 max-w-sm text-center">
              Pulled new commits — regenerating questions to reflect them
            </div>
          )}
          <div className="text-xs font-mono text-fg-subtle uppercase tracking-wider">
            {progress.pipeline
              ? `${progress.pipeline} pipeline`
              : "Pipeline running"}
          </div>
          <div className="text-sm text-fg">
            {progress.stage_label || "Working…"}
          </div>
          <div className="w-full max-w-sm h-2 bg-muted rounded-full overflow-hidden">
            <div
              className="h-full bg-primary transition-all duration-300 ease-out"
              style={{ width: `${Math.round(fraction * 100)}%` }}
            />
          </div>
          <div className="text-xs font-mono text-fg-subtle tabular-nums">
            Stage {progress.stage_index} / {progress.stage_total}
            {progress.sub_total > 0 &&
              ` · ${progress.sub_done}/${progress.sub_total}`}
          </div>
        </div>
      );
    }

    if (progressEnabled && progress?.status === "failed") {
      return (
        <div className="h-full flex flex-col items-center justify-center gap-4 p-6">
          <div className="text-danger text-sm font-medium">Pipeline failed</div>
          {progress.error && (
            <div className="text-xs font-mono text-fg-subtle max-w-sm text-center break-words">
              {progress.error}
            </div>
          )}
          <div className="text-xs text-fg-subtle">
            Go back home and try a different repo.
          </div>
        </div>
      );
    }

    if (dataLoading) {
      return (
        <div className="h-full flex flex-col items-center justify-center gap-4 p-6">
          <div className="text-sm font-mono text-fg-subtle">Loading…</div>
        </div>
      );
    }

    if (problems.length === 0) {
      return (
        <div className="h-full flex flex-col items-center justify-center gap-4 p-6">
          <div className="text-sm font-mono text-fg-subtle">Waiting for worker…</div>
        </div>
      );
    }

    return (
      <div className="h-full flex flex-col items-center justify-center gap-4 p-6">
        <div className="text-fg-subtle text-sm">
          {problems.length} problem{problems.length === 1 ? "" : "s"} ready
        </div>
        <button
          type="button"
          className="px-4 py-2 rounded-md bg-primary text-white text-sm font-medium cursor-pointer"
          onClick={beginQuiz}
        >
          Begin Quiz
        </button>
      </div>
    );
  }

  if (state.status === "in_progress") {
    const currentId = state.order[state.currentIndex];
    const current = problemsById.get(currentId);
    const total = state.order.length;
    const answer = state.answers[currentId];
    const submitted = answer !== undefined;

    if (!current) {
      return (
        <div className="h-full flex items-center justify-center p-6 text-center text-danger">
          Question {currentId} not found in current data set.
        </div>
      );
    }

    const submitAnswer = (a: UserAnswer) => {
      setState({
        ...state,
        answers: { ...state.answers, [currentId]: a },
      });
    };

    const goTo = (idx: number) => {
      if (idx < 0 || idx >= total || idx === state.currentIndex) return;
      setState({ ...state, currentIndex: idx });
    };

    const finish = () => {
      setState({
        status: "completed",
        startedAt: state.startedAt,
        finishedAt: Date.now(),
        order: state.order,
        answers: state.answers,
        optionOrders: state.optionOrders,
      });
    };

    const dotStatuses = state.order.map((id) => {
      const a = state.answers[id];
      const p = problemsById.get(id);
      if (!a || !p) return "unanswered" as const;
      return isAnswerCorrect(p, a)
        ? ("correct" as const)
        : ("incorrect" as const);
    });

    let renderer: React.ReactNode;
    switch (current.kind) {
      case "MCQ":
        renderer = (
          <MCQRenderer
            problem={current}
            options={
              state.optionOrders[currentId] ?? [
                current.correct,
                ...current.distractors,
              ]
            }
            selected={answer?.kind === "MCQ" ? answer.selected : undefined}
            onSubmit={(s) => submitAnswer({ kind: "MCQ", selected: s })}
          />
        );
        break;
      case "TF":
        renderer = (
          <TFRenderer
            problem={current}
            selected={answer?.kind === "TF" ? answer.selected : undefined}
            onSubmit={(s) => submitAnswer({ kind: "TF", selected: s })}
          />
        );
        break;
      case "MultipleSelect":
        renderer = (
          <MultipleSelectRenderer
            problem={current}
            options={
              state.optionOrders[currentId] ?? [
                ...current.correct,
                ...current.distractors,
              ]
            }
            selected={
              answer?.kind === "MultipleSelect" ? answer.selected : undefined
            }
            onSubmit={(s) =>
              submitAnswer({ kind: "MultipleSelect", selected: s })
            }
          />
        );
        break;
      case "Order":
        renderer = (
          <OrderRenderer
            problem={current}
            initialOrder={
              state.optionOrders[currentId] ?? current.correct_order
            }
            selected={answer?.kind === "Order" ? answer.ordered : undefined}
            onSubmit={(o) => submitAnswer({ kind: "Order", ordered: o })}
          />
        );
        break;
      case "Pairing":
        renderer = (
          <PairingRenderer
            problem={current}
            rightShuffled={
              state.optionOrders[currentId] ??
              current.pairs.map(([, r]) => r)
            }
            selected={answer?.kind === "Pairing" ? answer.pairs : undefined}
            onSubmit={(p) => submitAnswer({ kind: "Pairing", pairs: p })}
          />
        );
        break;
      case "Highlight":
        renderer = (
          <HighlightRenderer
            problem={current}
            repoId={repoId}
            selected={
              answer?.kind === "Highlight"
                ? answer.selectedLineIndices
                : undefined
            }
            onSubmit={(i) =>
              submitAnswer({ kind: "Highlight", selectedLineIndices: i })
            }
          />
        );
        break;
    }

    const correct = submitted && isAnswerCorrect(current, answer);

    return (
      <div className="h-full flex flex-col p-6 gap-4 overflow-y-auto">
        <div className="flex items-center justify-between">
          <div className="text-xs text-fg-subtle font-mono">
            Question {state.currentIndex + 1} of {total} · {current.kind}
          </div>
          <button
            type="button"
            onClick={finish}
            title="Finish quiz (unanswered count as incorrect)"
            className="text-xs font-mono px-2 py-1 rounded-md border border-border hover:bg-muted text-fg-muted cursor-pointer"
          >
            Finish Quiz
          </button>
        </div>
        <div className="text-lg text-fg whitespace-pre-wrap">
          <InlineText text={current.prompt} />
        </div>

        {renderer}

        {submitted && (
          <div className="flex flex-col gap-2 mt-2">
            <div
              className={`text-lg font-medium ${
                correct ? "text-success" : "text-danger"
              }`}
            >
              {correct ? "Correct" : "Incorrect"}
            </div>
            <div className="text-lg text-fg whitespace-pre-wrap">
              <InlineText text={current.explanation} />
            </div>
            {current.citations.length > 0 && current.kind !== "Highlight" && (
              <div className="text-xs font-mono flex flex-wrap gap-1.5">
                {current.citations.map((c) => {
                  const { path, line } = parseCitation(c);
                  const params = new URLSearchParams({ file: path });
                  if (line) params.set("line", line);
                  return (
                    <button
                      key={c}
                      type="button"
                      onClick={() => {
                        if (typeof window === "undefined") return;
                        const url = new URL(window.location.href);
                        const sameFile = url.searchParams.get("file") === path;
                        const sameLine =
                          url.searchParams.get("line") === (line ?? null);
                        if (sameFile && sameLine) {
                          window.dispatchEvent(
                            new CustomEvent("citation-flash", {
                              detail: { path, line },
                            }),
                          );
                        } else {
                          router.push(
                            `/quiz/${repoId}?${params.toString()}`,
                            { scroll: false },
                          );
                        }
                      }}
                      className="inline-flex items-center rounded-md border border-info-border bg-info-bg px-2 py-0.5 text-info-fg cursor-pointer transition-colors hover:bg-info-bg-hover hover:border-info-border-hover"
                    >
                      {c}
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        )}

        <div className="mt-auto pt-2 relative">
          {navOpen && (
            <div
              ref={navPopoverRef}
              className="absolute bottom-full mb-2 inset-x-0 bg-card border border-border rounded-md shadow-lg p-2 z-20"
            >
              <div className="flex flex-wrap gap-1.5 justify-center">
                {dotStatuses.map((status, i) => {
                  const isCurrent = i === state.currentIndex;
                  let cls =
                    "border-border bg-card text-fg-muted hover:bg-card-hover";
                  if (status === "correct")
                    cls =
                      "border-success-border bg-success-bg text-success-fg hover:opacity-80";
                  else if (status === "incorrect")
                    cls =
                      "border-danger-border bg-danger-bg text-danger-fg hover:opacity-80";
                  return (
                    <button
                      key={state.order[i]}
                      type="button"
                      aria-label={`Go to question ${i + 1}`}
                      title={`Question ${i + 1}`}
                      onClick={() => {
                        goTo(i);
                        setNavOpen(false);
                      }}
                      className={`w-7 h-7 rounded border text-xs font-mono cursor-pointer transition-colors flex items-center justify-center ${cls} ${
                        isCurrent
                          ? "ring-2 ring-selection-border ring-offset-1 ring-offset-card"
                          : ""
                      }`}
                    >
                      {i + 1}
                    </button>
                  );
                })}
              </div>
            </div>
          )}
          <div className="flex items-center gap-3">
            <button
              type="button"
              aria-label="Previous question"
              disabled={state.currentIndex === 0}
              onClick={() => goTo(state.currentIndex - 1)}
              className="shrink-0 p-2 rounded-md border border-border hover:bg-muted text-fg-muted cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-transparent"
            >
              <svg
                className="w-4 h-4"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <polyline points="15 18 9 12 15 6" />
              </svg>
            </button>
            <div className="flex-1 flex justify-center">
              <button
                ref={navTriggerRef}
                type="button"
                onClick={() => setNavOpen((o) => !o)}
                aria-expanded={navOpen}
                aria-label="Question navigator"
                className="px-3 py-1.5 rounded-md border border-border hover:bg-muted text-fg-muted text-sm font-mono cursor-pointer"
              >
                {state.currentIndex + 1} / {total}
              </button>
            </div>
            <button
              type="button"
              aria-label="Next question"
              disabled={state.currentIndex === total - 1}
              onClick={() => goTo(state.currentIndex + 1)}
              className="shrink-0 p-2 rounded-md border border-border hover:bg-muted text-fg-muted cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-transparent"
            >
              <svg
                className="w-4 h-4"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <polyline points="9 6 15 12 9 18" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    );
  }

  const total = state.order.length;
  const correctCount = state.order.reduce((acc, id) => {
    const p = problemsById.get(id);
    const a = state.answers[id];
    if (p && a && isAnswerCorrect(p, a)) return acc + 1;
    return acc;
  }, 0);
  const pct = total > 0 ? Math.round((correctCount / total) * 100) : 0;

  const perConcept = new Map<
    string,
    { title: string; correct: number; total: number }
  >();
  for (const id of state.order) {
    const p = problemsById.get(id);
    if (!p) continue;
    const cid = p.concept_id ?? p.concept_group_id ?? "_other";
    const entry = perConcept.get(cid) ?? {
      title: topicTitles[cid] ?? "Other",
      correct: 0,
      total: 0,
    };
    entry.total += 1;
    const a = state.answers[id];
    if (a && isAnswerCorrect(p, a)) entry.correct += 1;
    perConcept.set(cid, entry);
  }
  const conceptRows = Array.from(perConcept.entries())
    .map(([cid, v]) => ({ cid, ...v }))
    .sort((a, b) => b.correct / b.total - a.correct / a.total);

  return (
    <CompletionView
      total={total}
      correctCount={correctCount}
      pct={pct}
      conceptRows={conceptRows}
      onRestart={() => setState({ status: "not_started" })}
    />
  );
}

function CompletionView({
  total,
  correctCount,
  pct,
  conceptRows,
  onRestart,
}: {
  total: number;
  correctCount: number;
  pct: number;
  conceptRows: { cid: string; title: string; correct: number; total: number }[];
  onRestart: () => void;
}) {
  const animatedCount = useCountUp(correctCount, COMPLETION_ANIM_MS);
  const animatedPct = useCountUp(pct, COMPLETION_ANIM_MS);

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="max-w-xl mx-auto flex flex-col gap-6">
        <div className="text-center">
          <div className="text-xs font-mono text-fg-subtle uppercase tracking-wider">
            Quiz complete
          </div>
        </div>

        <div className="flex flex-col items-center gap-2 py-4 border border-border rounded-xl bg-card">
          <div className="text-6xl font-bold text-fg tabular-nums">
            {animatedCount}
            <span className="text-fg-faint font-normal">/{total}</span>
          </div>
          <div className="text-sm text-fg-muted tabular-nums">
            correct ({animatedPct}%)
          </div>
        </div>

        {conceptRows.length > 0 && (
          <div className="flex flex-col gap-3">
            <div className="text-xs font-mono text-fg-subtle uppercase tracking-wider">
              By concept
            </div>
            <div className="flex flex-col gap-3">
              {conceptRows.map((row) => {
                const ratio = row.total > 0 ? row.correct / row.total : 0;
                const barColor =
                  ratio === 1
                    ? "bg-green-500"
                    : ratio >= 0.5
                      ? "bg-blue-500"
                      : ratio > 0
                        ? "bg-amber-500"
                        : "bg-red-500";
                return (
                  <ConceptRow
                    key={row.cid}
                    title={row.title}
                    correct={row.correct}
                    total={row.total}
                    color={barColor}
                  />
                );
              })}
            </div>
          </div>
        )}

        <div className="flex flex-col items-center gap-3 pt-2">
          <button
            type="button"
            className="px-4 py-2 rounded-md bg-primary text-white text-sm font-medium cursor-pointer"
            onClick={onRestart}
          >
            Restart Quiz
          </button>
        </div>
      </div>
    </div>
  );
}
