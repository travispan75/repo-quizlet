import { codeToHtml } from "shiki";
import { backend } from "@/lib/backend";
import { langForFile } from "@/lib/repo";
import type { Highlight, HighlightSnippet } from "@/lib/problems";

function parseCitation(
  s: string,
): { path: string; startLine: number; endLine: number } | null {
  const lastColon = s.lastIndexOf(":");
  if (lastColon < 0) return null;
  const filePath = s.slice(0, lastColon);
  const range = s.slice(lastColon + 1);
  const dash = range.indexOf("-");
  if (dash >= 0) {
    const start = parseInt(range.slice(0, dash), 10);
    const end = parseInt(range.slice(dash + 1), 10);
    if (!Number.isFinite(start) || !Number.isFinite(end)) return null;
    return { path: filePath, startLine: start, endLine: end };
  }
  const line = parseInt(range, 10);
  if (!Number.isFinite(line)) return null;
  return { path: filePath, startLine: line, endLine: line };
}

function splitShikiLines(html: string): { lines: string[]; preStyle: string } {
  const preMatch = html.match(/<pre[^>]*style="([^"]*)"[^>]*>/);
  const preStyle = preMatch?.[1] ?? "";
  const codeMatch = html.match(/<code[^>]*>([\s\S]*?)<\/code>/);
  if (!codeMatch) return { lines: [], preStyle };
  let inner = codeMatch[1];
  inner = inner.replace(/^\n+|\n+$/g, "");
  const rawLines = inner.split(/\n(?=<span class="line">)/);
  const lines = rawLines.map((raw) => {
    const m = raw.match(/^<span class="line">([\s\S]*)<\/span>$/);
    return m ? m[1] : raw;
  });
  return { lines, preStyle };
}

export async function enrichHighlight(
  problem: Highlight,
  repoId: string,
): Promise<Highlight> {
  const blockParsed = parseCitation(problem.block);
  if (!blockParsed) {
    return { ...problem, snippet: makeError("Invalid block citation") };
  }

  let file;
  try {
    file = await backend.getFile(repoId, blockParsed.path);
  } catch {
    return { ...problem, snippet: makeError("File not found", blockParsed) };
  }
  if (file.binary || file.contents == null) {
    return { ...problem, snippet: makeError("Binary file", blockParsed) };
  }

  const fullLines = file.contents.split("\n");
  const start = Math.max(1, blockParsed.startLine);
  const end = Math.min(fullLines.length, blockParsed.endLine);
  if (end < start) {
    return { ...problem, snippet: makeError("Empty range", blockParsed) };
  }
  const sliced = fullLines.slice(start - 1, end).join("\n");

  const basename = blockParsed.path.split("/").pop() ?? "";
  const lang = file.language ?? langForFile(basename);

  const themes = { light: "github-light", dark: "github-dark" };
  let html: string;
  try {
    html = await codeToHtml(sliced, { lang, themes });
  } catch {
    html = await codeToHtml(sliced, { lang: "text", themes });
  }
  const { lines, preStyle } = splitShikiLines(html);

  const correctLines = new Set<number>();
  for (const c of problem.correct) {
    const parsed = parseCitation(c);
    if (!parsed || parsed.path !== blockParsed.path) continue;
    const lo = Math.max(start, parsed.startLine);
    const hi = Math.min(end, parsed.endLine);
    for (let i = lo; i <= hi; i++) correctLines.add(i);
  }

  const snippet: HighlightSnippet = {
    path: blockParsed.path,
    startLine: start,
    endLine: end,
    lines,
    preStyle,
    correctLines: Array.from(correctLines).sort((a, b) => a - b),
  };
  return { ...problem, snippet };
}

function makeError(
  msg: string,
  parsed?: { path: string; startLine: number; endLine: number },
): HighlightSnippet {
  return {
    path: parsed?.path ?? "",
    startLine: parsed?.startLine ?? 0,
    endLine: parsed?.endLine ?? 0,
    lines: [],
    preStyle: "",
    correctLines: [],
    error: msg,
  };
}
