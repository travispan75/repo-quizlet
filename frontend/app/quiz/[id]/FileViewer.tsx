"use client";

import { useCallback, useEffect, useRef } from "react";
import { useSearchParams } from "next/navigation";
import Tabs from "./Tabs";

const FLASH_MS = 2000;

export default function FileViewer({
  repoId,
  children,
}: {
  repoId: string;
  children: React.ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const searchParams = useSearchParams();
  const line = searchParams.get("line");
  const file = searchParams.get("file");

  const flashLines = useCallback((lineSpec: string | null) => {
    if (!ref.current || !lineSpec) return;

    const m = lineSpec.match(/^(\d+)(?:-(\d+))?$/);
    if (!m) return;

    const start = parseInt(m[1], 10);
    const end = m[2] ? parseInt(m[2], 10) : start;

    const els = ref.current.querySelectorAll<HTMLElement>(".line");
    if (els.length === 0) return;

    const first = els[start - 1];
    if (!first) return;

    first.scrollIntoView({ block: "center" });

    if (timeoutRef.current) clearTimeout(timeoutRef.current);

    const flashed: HTMLElement[] = [];
    for (let i = start - 1; i <= end - 1 && i < els.length; i++) {
      els[i].classList.remove("citation-flash");
      void els[i].offsetWidth;
      els[i].classList.add("citation-flash");
      flashed.push(els[i]);
    }

    timeoutRef.current = setTimeout(() => {
      for (const el of flashed) el.classList.remove("citation-flash");
      timeoutRef.current = null;
    }, FLASH_MS);
  }, []);

  useEffect(() => {
    flashLines(line);
  }, [line, flashLines]);

  useEffect(() => {
    function handler(e: Event) {
      const ce = e as CustomEvent<{ path: string; line: string | null }>;
      if (ce.detail.path !== file) return;
      flashLines(ce.detail.line);
    }
    window.addEventListener("citation-flash", handler as EventListener);
    return () =>
      window.removeEventListener("citation-flash", handler as EventListener);
  }, [file, flashLines]);

  return (
    <div className="h-full flex flex-col">
      <Tabs repoId={repoId} />
      <div
        ref={ref}
        className="scroll-on-hover flex-1 overflow-y-auto overflow-x-hidden"
      >
        {children}
      </div>
    </div>
  );
}
