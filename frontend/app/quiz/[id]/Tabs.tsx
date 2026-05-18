"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

type Tab = { path: string; preview: boolean };

function storageKey(repoId: string) {
  return `tabs:${repoId}`;
}

function basename(p: string) {
  const i = p.lastIndexOf("/");
  return i >= 0 ? p.slice(i + 1) : p;
}

function isValidTabs(x: unknown): x is Tab[] {
  if (!Array.isArray(x)) return false;
  return x.every(
    (t) =>
      t !== null &&
      typeof t === "object" &&
      typeof (t as { path?: unknown }).path === "string" &&
      typeof (t as { preview?: unknown }).preview === "boolean",
  );
}

export default function Tabs({ repoId }: { repoId: string }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const activeFile = searchParams.get("file");

  const [tabs, setTabs] = useState<Tab[] | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const justClosedRef = useRef<string | null>(null);
  const [thumb, setThumb] = useState({ left: 0, width: 0, visible: false });
  const [hovering, setHovering] = useState(false);
  const [dragging, setDragging] = useState(false);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;

    function update() {
      if (!el) return;
      const ratio = el.clientWidth / el.scrollWidth;
      if (ratio >= 1 || !Number.isFinite(ratio)) {
        setThumb((t) => (t.visible ? { ...t, visible: false } : t));
        return;
      }
      setThumb({
        left: (el.scrollLeft / el.scrollWidth) * 100,
        width: ratio * 100,
        visible: true,
      });
    }

    update();
    el.addEventListener("scroll", update, { passive: true });
    const ro = new ResizeObserver(update);
    ro.observe(el);
    for (const child of Array.from(el.children)) ro.observe(child);
    return () => {
      el.removeEventListener("scroll", update);
      ro.disconnect();
    };
  }, [tabs]);

  useEffect(() => {
    if (!activeFile || !scrollRef.current) return;
    const el = scrollRef.current.querySelector<HTMLElement>(
      `[data-tab-path="${CSS.escape(activeFile)}"]`,
    );
    if (el) {
      el.scrollIntoView({
        inline: "nearest",
        block: "nearest",
        behavior: "smooth",
      });
    }
  }, [activeFile, tabs]);

  useEffect(() => {
    const raw = localStorage.getItem(storageKey(repoId));
    if (raw) {
      try {
        const parsed = JSON.parse(raw);
        if (isValidTabs(parsed)) {
          setTabs(parsed);
          return;
        }
      } catch {}
    }
    setTabs([]);
  }, [repoId]);

  useEffect(() => {
    if (tabs === null) return;
    localStorage.setItem(storageKey(repoId), JSON.stringify(tabs));
  }, [tabs, repoId]);

  useEffect(() => {
    if (tabs === null || !activeFile) {
      justClosedRef.current = null;
      return;
    }
    if (justClosedRef.current === activeFile) return;
    justClosedRef.current = null;
    setTabs((prev) => {
      if (prev === null) return prev;
      if (prev.some((t) => t.path === activeFile)) return prev;
      const previewIdx = prev.findIndex((t) => t.preview);
      if (previewIdx >= 0) {
        const next = prev.slice();
        next[previewIdx] = { path: activeFile, preview: true };
        return next;
      }
      return [...prev, { path: activeFile, preview: true }];
    });
  }, [activeFile, tabs]);

  useEffect(() => {
    function handler(e: Event) {
      const detail = (e as CustomEvent).detail as { path?: unknown };
      if (typeof detail?.path !== "string") return;
      const path = detail.path;
      setTabs((prev) => {
        if (prev === null) return prev;
        if (prev.some((t) => t.path === path)) {
          return prev.map((t) =>
            t.path === path ? { ...t, preview: false } : t,
          );
        }
        return [...prev, { path, preview: false }];
      });
    }
    window.addEventListener("pin-file", handler);
    return () => window.removeEventListener("pin-file", handler);
  }, []);

  if (tabs === null) {
    return (
      <div className="h-9 border-b border-border bg-surface shrink-0" />
    );
  }

  function navTo(path: string | null) {
    if (path === null) {
      router.push(`/quiz/${repoId}`, { scroll: false });
    } else {
      router.push(`/quiz/${repoId}?file=${encodeURIComponent(path)}`, {
        scroll: false,
      });
    }
  }

  function handleTabClick(path: string) {
    if (path === activeFile) {
      setTabs((prev) =>
        prev === null
          ? prev
          : prev.map((t) =>
              t.path === path && t.preview ? { ...t, preview: false } : t,
            ),
      );
    } else {
      navTo(path);
    }
  }

  function handleClose(path: string) {
    if (tabs === null) return;
    const idx = tabs.findIndex((t) => t.path === path);
    const newTabs = tabs.filter((t) => t.path !== path);
    setTabs(newTabs);
    if (activeFile === path) {
      justClosedRef.current = path;
      const fallback =
        newTabs.length > 0
          ? newTabs[Math.min(idx, newTabs.length - 1)].path
          : null;
      navTo(fallback);
    }
  }

  return (
    <div
      className="relative shrink-0 h-9 border-b border-border bg-surface"
      onMouseEnter={() => setHovering(true)}
      onMouseLeave={() => setHovering(false)}
    >
      <div
        ref={scrollRef}
        className="tabs-scroll absolute inset-0 flex overflow-x-auto overflow-y-hidden overscroll-x-contain"
      >
        {tabs.map((tab) => {
          const isActive = tab.path === activeFile;
          return (
            <div
              key={tab.path}
              data-tab-path={tab.path}
              className={`shrink-0 flex items-center gap-2 px-3 border-r border-border text-xs font-mono whitespace-nowrap cursor-pointer ${
                isActive
                  ? "bg-card text-fg"
                  : "text-fg-muted hover:bg-muted"
              } ${tab.preview ? "italic" : ""}`}
              onClick={(e) => {
                e.currentTarget.scrollIntoView({
                  inline: "nearest",
                  block: "nearest",
                  behavior: "smooth",
                });
                handleTabClick(tab.path);
              }}
            >
              <span>{basename(tab.path)}</span>
              <span
                role="button"
                aria-label="Close"
                className="text-fg-subtle hover:text-fg px-1 leading-none text-base"
                onClick={(e) => {
                  e.stopPropagation();
                  handleClose(tab.path);
                }}
              >
                ×
              </span>
            </div>
          );
        })}
      </div>
      {thumb.visible && (
        <div
          className="absolute bottom-0 h-[3px] bg-[var(--scrollbar-thumb)] transition-opacity cursor-grab active:cursor-grabbing"
          style={{
            left: `${thumb.left}%`,
            width: `${thumb.width}%`,
            opacity: hovering || dragging ? 1 : 0,
          }}
          onMouseDown={(e) => {
            e.preventDefault();
            const el = scrollRef.current;
            if (!el) return;
            const startX = e.clientX;
            const startScrollLeft = el.scrollLeft;
            const ratio = el.scrollWidth / el.clientWidth;

            setDragging(true);
            document.body.style.userSelect = "none";

            const onMove = (ev: MouseEvent) => {
              el.scrollLeft = startScrollLeft + (ev.clientX - startX) * ratio;
            };
            const onUp = () => {
              document.removeEventListener("mousemove", onMove);
              document.removeEventListener("mouseup", onUp);
              document.body.style.userSelect = "";
              setDragging(false);
            };
            document.addEventListener("mousemove", onMove);
            document.addEventListener("mouseup", onUp);
          }}
        />
      )}
    </div>
  );
}
