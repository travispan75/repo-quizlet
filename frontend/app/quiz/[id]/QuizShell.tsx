"use client";

import { use, useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { backend, BackendError, type TreeNode } from "@/lib/backend";
import { decodeProblem, type Problem } from "@/lib/problems";
import { enrichHighlight } from "@/lib/highlight";
import ResizableLayout from "./ResizableLayout";
import FileTree from "./FileTree";
import QuizPane from "./QuizPane";
import FileViewer from "./FileViewer";
import SidebarHeader from "./SidebarHeader";

export default function QuizShell({
  params,
  children,
}: {
  params: Promise<{ id: string }>;
  children: React.ReactNode;
}) {
  const { id } = use(params);
  const router = useRouter();

  const [repoName, setRepoName] = useState(id.slice(0, 8));
  const [tree, setTree] = useState<TreeNode[]>([]);
  const [problems, setProblems] = useState<Problem[]>([]);
  const [topicTitles, setTopicTitles] = useState<Record<string, string>>({});
  const [problemsError, setProblemsError] = useState<string | undefined>();
  const [notFound, setNotFound] = useState(false);
  const [dataLoading, setDataLoading] = useState(true);

  const loadQuizData = useCallback(async () => {
    setDataLoading(true);
    setNotFound(false);
    setProblemsError(undefined);

    try {
      const repo = await backend.getRepo(id);
      setRepoName(repo.name);

      const [treeRes, problemsRes, topicsRes] = await Promise.all([
        backend.getTree(id).catch((e) => {
          if (e instanceof BackendError && e.status === 404) {
            return { tree: [] as TreeNode[] };
          }
          throw e;
        }),
        backend.getProblems(id),
        backend.getTopics(id),
      ]);

      setTree(treeRes.tree);
      setTopicTitles({
        ...topicsRes.cluster_titles,
        ...topicsRes.concept_group_labels,
      });

      const decoded = problemsRes.problems.map(decodeProblem);
      const enriched = await Promise.all(
        decoded.map((p) =>
          p.kind === "Highlight" ? enrichHighlight(p, id) : Promise.resolve(p),
        ),
      );
      setProblems(enriched);
    } catch (e) {
      if (e instanceof BackendError && e.status === 404) {
        setNotFound(true);
        return;
      }
      setProblemsError("Couldn't load quiz questions. Please try again later.");
    } finally {
      setDataLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadQuizData();
  }, [loadQuizData]);

  useEffect(() => {
    if (notFound) router.replace("/");
  }, [notFound, router]);

  if (notFound) return null;

  return (
    <ResizableLayout
      sidebar={
        <div className="flex flex-col h-full">
          <SidebarHeader repoName={repoName} />
          <div className="p-2 flex-1 overflow-y-auto overflow-x-hidden scroll-on-hover">
            {dataLoading && tree.length === 0 ? (
              <div className="text-xs font-mono text-fg-subtle px-1">Loading tree…</div>
            ) : (
              <FileTree nodes={tree} repoId={id} />
            )}
          </div>
        </div>
      }
      viewer={<FileViewer repoId={id}>{children}</FileViewer>}
      right={
        <QuizPane
          repoId={id}
          problems={problems}
          topicTitles={topicTitles}
          error={problemsError}
          dataLoading={dataLoading}
          onPipelineDone={loadQuizData}
        />
      }
    />
  );
}
