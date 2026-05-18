// Thin HTTP client to the FastAPI backend.
//
// The frontend is stateless: this module is the ONLY place that reaches the
// backend. Both server-rendered pages and client components hit the same
// base URL via NEXT_PUBLIC_BACKEND_URL so the API surface stays unified.

const BASE_URL = (
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:5000"
).replace(/\/+$/, "");

export function backendUrl(): string {
  return BASE_URL;
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, { cache: "no-store" });
  if (!res.ok) {
    throw new BackendError(res.status, await safeText(res));
  }
  return (await res.json()) as T;
}

async function safeText(res: Response): Promise<string> {
  try {
    return await res.text();
  } catch {
    return "";
  }
}

export class BackendError extends Error {
  constructor(public status: number, public body: string) {
    super(`backend ${status}: ${body.slice(0, 200)}`);
  }
}

export type RepoListItem = {
  id: string;
  name: string;
  url: string;
  indexed_at: string | null;
};

export type ProgressPayload = {
  status: "idle" | "running" | "done" | "failed";
  pipeline?: string;
  stage?: string;
  stage_label?: string;
  stage_index?: number;
  stage_total?: number;
  sub_done?: number;
  sub_total?: number;
  repo_updated?: boolean;
  updated_at?: number;
  error?: string;
};

export type TreeNode = {
  name: string;
  path: string;
  type: "file" | "dir";
  children?: TreeNode[];
};

export type FileResponse =
  | { path: string; binary: true; size: number; contents?: undefined; language?: undefined }
  | { path: string; binary: false; size: number; language: string; contents: string };

export type SubmitResponse = { id: string };

export type ProblemKind =
  | "MCQ"
  | "TF"
  | "MultipleSelect"
  | "Order"
  | "Pairing"
  | "Highlight";

export type ProblemRow = {
  problem_id: string;
  concept_id: string | null;
  concept_group_id: string | null;
  kind: ProblemKind;
  prompt: string;
  explanation: string;
  citations: string[];
  payload: Record<string, unknown>;
};

export type TopicsResponse = {
  cluster_titles: Record<string, string>;
  concept_group_labels: Record<string, string>;
};

export const backend = {
  async submitRepo(url: string): Promise<SubmitResponse> {
    const res = await fetch(`${BASE_URL}/api/repos`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    if (!res.ok) {
      const body = (await res.json().catch(() => null)) as { error?: string } | null;
      throw new BackendError(res.status, body?.error ?? "");
    }
    return (await res.json()) as SubmitResponse;
  },

  listRepos: () => getJson<RepoListItem[]>("/api/repos"),

  getRepo: (id: string) => getJson<RepoListItem>(`/api/repos/${id}`),

  getProgress: (id: string) => getJson<ProgressPayload>(`/api/repos/${id}/progress`),

  getTree: (id: string) => getJson<{ tree: TreeNode[] }>(`/api/repos/${id}/tree`),

  getFile: (id: string, path: string) =>
    getJson<FileResponse>(`/api/repos/${id}/file?path=${encodeURIComponent(path)}`),

  getProblems: (id: string) =>
    getJson<{ problems: ProblemRow[] }>(`/api/repos/${id}/problems`),

  getTopics: (id: string) => getJson<TopicsResponse>(`/api/repos/${id}/topics`),
};
