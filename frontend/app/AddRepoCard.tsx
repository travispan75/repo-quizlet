"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { backend } from "@/lib/backend";

const REPO_SUBMIT_DISABLED =
  process.env.NEXT_PUBLIC_DISABLE_REPO_SUBMIT === "true";

export default function AddRepoCard() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !loading) close();
    };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    setTimeout(() => inputRef.current?.focus(), 0);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open, loading]);

  function close() {
    setOpen(false);
    setUrl("");
    setError(null);
  }

  async function loadRepo() {
    if (loading || !url.trim()) return;
    setLoading(true);
    setError(null);

    if (REPO_SUBMIT_DISABLED) {
      setError(
        "Sorry, I can't afford tokens lol. You can run it locally.",
      );
      setLoading(false);
      return;
    }

    try {
      const { id } = await backend.submitRepo(url.trim());
      router.push(`/quiz/${id}`);
    } catch (e) {
      setError(
        e instanceof Error && e.message ? e.message : "Couldn't reach the server",
      );
      setLoading(false);
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="group aspect-[5/3] flex flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed border-border bg-card/40 text-fg-subtle hover:bg-card-hover hover:border-border-hover hover:text-fg-muted cursor-pointer transition-colors"
      >
        <svg
          className="w-10 h-10"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M12 5v14M5 12h14" />
        </svg>
        <div className="text-sm font-medium">Add a repo</div>
      </button>

      {open && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/40 backdrop-blur-sm"
          onClick={() => {
            if (!loading) close();
          }}
        >
          <div
            className="w-full max-w-md rounded-xl border border-border bg-card shadow-2xl p-6 flex flex-col gap-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between">
              <div className="text-base font-medium text-fg">Analyze a repo</div>
              <button
                type="button"
                aria-label="Close"
                onClick={close}
                disabled={loading}
                className="p-1 rounded-md text-fg-subtle hover:bg-muted hover:text-fg cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <svg
                  className="w-4 h-4"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M18 6L6 18M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="text-xs text-fg-subtle">
              Paste a public GitHub, GitLab, or Bitbucket URL. We&apos;ll clone
              it, analyze the codebase, and generate a quiz.
            </div>

            <input
              ref={inputRef}
              placeholder="https://github.com/owner/repo"
              value={url}
              disabled={loading}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") loadRepo();
              }}
              className="border border-border bg-background text-fg placeholder:text-fg-faint rounded-md px-3 py-2 text-sm w-full disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-selection-border/40 focus:border-selection-border"
            />

            {error && (
              <div className="text-xs text-danger-fg bg-danger-bg border border-danger-border/40 rounded-md px-3 py-2">
                {error}
              </div>
            )}

            <button
              onClick={loadRepo}
              disabled={loading || !url.trim()}
              className="px-4 py-2 rounded-md bg-primary text-white text-sm font-medium cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed hover:bg-primary-hover transition-colors"
            >
              {loading ? "Loading…" : "Analyze"}
            </button>
          </div>
        </div>
      )}
    </>
  );
}
