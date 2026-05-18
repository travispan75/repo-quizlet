import { backend, BackendError, type ProblemRow, type RepoListItem } from "@/lib/backend";

export type ProblemKind =
  | "MCQ"
  | "TF"
  | "MultipleSelect"
  | "Order"
  | "Pairing"
  | "Highlight";

type ProblemBase = {
  problem_id: string;
  concept_id: string | null;
  concept_group_id: string | null;
  prompt: string;
  explanation: string;
  citations: string[];
};

export type MCQ = ProblemBase & {
  kind: "MCQ";
  correct: string;
  distractors: string[];
};

export type TF = ProblemBase & { kind: "TF"; is_true: boolean };

export type MultipleSelect = ProblemBase & {
  kind: "MultipleSelect";
  correct: string[];
  distractors: string[];
};

export type Order = ProblemBase & { kind: "Order"; correct_order: string[] };

export type Pairing = ProblemBase & {
  kind: "Pairing";
  pairs: [string, string][];
};

export type HighlightSnippet = {
  path: string;
  startLine: number;
  endLine: number;
  lines: string[];
  preStyle: string;
  correctLines: number[];
  error?: string;
};

export type Highlight = ProblemBase & {
  kind: "Highlight";
  block: string;
  correct: string[];
  snippet?: HighlightSnippet;
};

export type Problem = MCQ | TF | MultipleSelect | Order | Pairing | Highlight;

export type { RepoListItem } from "@/lib/backend";

export function decodeProblem(row: ProblemRow): Problem {
  const base: ProblemBase = {
    problem_id: row.problem_id,
    concept_id: row.concept_id,
    concept_group_id: row.concept_group_id,
    prompt: row.prompt,
    explanation: row.explanation,
    citations: row.citations,
  };
  const p = row.payload;
  switch (row.kind) {
    case "MCQ":
      return { ...base, kind: "MCQ", correct: p.correct as string, distractors: p.distractors as string[] };
    case "TF":
      return { ...base, kind: "TF", is_true: p.is_true as boolean };
    case "MultipleSelect":
      return {
        ...base,
        kind: "MultipleSelect",
        correct: p.correct as string[],
        distractors: p.distractors as string[],
      };
    case "Order":
      return { ...base, kind: "Order", correct_order: p.correct_order as string[] };
    case "Pairing":
      return { ...base, kind: "Pairing", pairs: p.pairs as [string, string][] };
    case "Highlight":
      return { ...base, kind: "Highlight", block: p.block as string, correct: p.correct as string[] };
    default:
      throw new Error(`Unknown problem kind: ${row.kind}`);
  }
}

export async function getProblems(repoId: string): Promise<Problem[]> {
  const { problems } = await backend.getProblems(repoId);
  return problems.map(decodeProblem);
}

export async function getRepos(): Promise<RepoListItem[]> {
  return backend.listRepos();
}

export async function getRepoById(repoId: string): Promise<RepoListItem | null> {
  try {
    return await backend.getRepo(repoId);
  } catch (e) {
    if (e instanceof BackendError && e.status === 404) return null;
    throw e;
  }
}

export async function getTopicTitles(repoId: string): Promise<Record<string, string>> {
  const { cluster_titles, concept_group_labels } = await backend.getTopics(repoId);
  return { ...cluster_titles, ...concept_group_labels };
}
