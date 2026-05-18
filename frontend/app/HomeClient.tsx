"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { backend, type RepoListItem } from "@/lib/backend";
import AddRepoCard from "./AddRepoCard";
import HomeRefresher from "./HomeRefresher";

function timeAgo(iso: string): string {
  const then = new Date(iso).getTime();
  const sec = Math.max(1, Math.floor((Date.now() - then) / 1000));
  if (sec < 60) return `${sec}s ago`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.floor(hr / 24);
  if (day < 30) return `${day}d ago`;
  const mo = Math.floor(day / 30);
  if (mo < 12) return `${mo}mo ago`;
  return `${Math.floor(mo / 12)}y ago`;
}

function ownerRepo(url: string): string {
  try {
    const u = new URL(url);
    const parts = u.pathname.split("/").filter(Boolean);
    if (parts.length >= 2) return `${parts[0]}/${parts[1]}`;
    return parts[0] ?? url;
  } catch {
    return url;
  }
}

function RepoCard({ repo }: { repo: RepoListItem }) {
  const inFlight = repo.indexed_at === null;
  return (
    <Link
      href={`/quiz/${repo.id}`}
      className={
        inFlight
          ? "group aspect-[5/3] flex flex-col justify-between rounded-xl border border-info-border/60 bg-card p-5 hover:bg-card-hover hover:border-info-border-hover transition-colors"
          : "group aspect-[5/3] flex flex-col justify-between rounded-xl border border-border bg-card p-5 hover:bg-card-hover hover:border-border-hover transition-colors"
      }
    >
      <div className="flex flex-col gap-1 min-w-0">
        <div className="text-xs font-mono text-fg-faint truncate">
          {ownerRepo(repo.url)}
        </div>
        <div className="text-xl font-semibold text-fg truncate">{repo.name}</div>
      </div>
      <div className="flex items-center justify-between text-xs">
        {inFlight ? (
          <span className="inline-flex items-center gap-2 font-mono text-info-fg">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full rounded-full bg-info-fg opacity-60 animate-ping" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-info-fg" />
            </span>
            analyzing…
          </span>
        ) : (
          <span className="font-mono text-fg-subtle">
            analyzed {timeAgo(repo.indexed_at!)}
          </span>
        )}
        <span className="opacity-0 group-hover:opacity-100 transition-opacity text-fg-muted inline-flex items-center gap-1">
          {inFlight ? "watch" : "open"}
          <svg
            className="w-3 h-3"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <polyline points="9 6 15 12 9 18" />
          </svg>
        </span>
      </div>
    </Link>
  );
}

function RepoCardSkeleton() {
  return (
    <div className="aspect-[5/3] rounded-xl border border-border bg-card p-5 animate-pulse">
      <div className="h-3 w-24 bg-muted rounded mb-3" />
      <div className="h-6 w-32 bg-muted rounded" />
    </div>
  );
}

export default function HomeClient() {
  const [repos, setRepos] = useState<RepoListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    backend
      .listRepos()
      .then((data) => {
        if (!cancelled) setRepos(data);
      })
      .catch(() => {
        if (!cancelled) setError("Couldn't load repos.");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const inFlightCount =
    repos?.filter((r) => r.indexed_at === null).length ?? 0;
  const readyCount = repos ? repos.length - inFlightCount : 0;

  const subtitle =
    repos === null
      ? "Loading…"
      : error
        ? error
        : repos.length === 0
          ? "No repos yet — add one to get started."
          : inFlightCount > 0
            ? `${readyCount} ready, ${inFlightCount} analyzing`
            : `${readyCount} repo${readyCount === 1 ? "" : "s"} ready`;

  return (
    <div className="min-h-screen bg-background">
      <HomeRefresher enabled={inFlightCount > 0} />
      <div className="max-w-6xl mx-auto px-6 py-12 flex flex-col gap-8">
        <div className="flex flex-col gap-1">
          <div className="text-xs font-mono text-fg-subtle uppercase tracking-wider">
            Repo quiz
          </div>
          <h1 className="text-2xl font-semibold text-fg">
            Pick a repo to quiz yourself on
          </h1>
          <div className="text-sm text-fg-muted">{subtitle}</div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {repos === null
            ? Array.from({ length: 3 }, (_, i) => <RepoCardSkeleton key={i} />)
            : repos.map((r) => <RepoCard key={r.id} repo={r} />)}
          <AddRepoCard />
        </div>
      </div>
    </div>
  );
}
