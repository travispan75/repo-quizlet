"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { codeToHtml } from "shiki";
import { backend, BackendError } from "@/lib/backend";
import { langForFile } from "@/lib/repo";

export default function FileContent({ repoId }: { repoId: string }) {
  const searchParams = useSearchParams();
  const file = searchParams.get("file");

  const [html, setHtml] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!file) {
      setHtml(null);
      setMessage(null);
      return;
    }

    let cancelled = false;
    setHtml(null);
    setMessage(null);

    (async () => {
      try {
        const fileResp = await backend.getFile(repoId, file);
        if (cancelled) return;

        if (fileResp.binary) {
          setMessage("Binary file — not displayed.");
          return;
        }

        const basename = file.split("/").pop() ?? "";
        const lang = fileResp.language ?? langForFile(basename);
        const themes = { light: "github-light", dark: "github-dark" };
        let out: string;
        try {
          out = await codeToHtml(fileResp.contents, { lang, themes });
        } catch {
          out = await codeToHtml(fileResp.contents, { lang: "text", themes });
        }
        out = out.replace(
          /<\/span>\n<span class="line">/g,
          '</span><span class="line">',
        );
        if (!cancelled) setHtml(out);
      } catch (e) {
        if (cancelled) return;
        if (e instanceof BackendError && e.status === 404) {
          setMessage("File not found.");
        } else if (e instanceof BackendError && e.status === 413) {
          setMessage("File too large to display.");
        } else {
          setMessage("Couldn't load file.");
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [repoId, file]);

  if (!file) return <CenterMessage>Select a file</CenterMessage>;
  if (message) return <CenterMessage>{message}</CenterMessage>;
  if (!html) return <CenterMessage>Loading…</CenterMessage>;

  return (
    <div
      className="text-sm [&>pre]:py-3 [&>pre]:pl-0 [&>pre]:pr-3 [&>pre]:whitespace-pre-wrap [&>pre]:break-words"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

function CenterMessage({ children }: { children: React.ReactNode }) {
  return (
    <div className="h-full flex items-center justify-center text-xs text-fg-subtle font-mono">
      {children}
    </div>
  );
}
