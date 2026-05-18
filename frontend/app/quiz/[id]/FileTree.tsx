"use client";

import { useRouter, useSearchParams } from "next/navigation";
import type { TreeNode } from "@/lib/repo";

export default function FileTree({
  nodes,
  repoId,
}: {
  nodes: TreeNode[];
  repoId: string;
}) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const activePath = searchParams.get("file") ?? undefined;

  return (
    <ul className="text-sm font-mono">
      {nodes.map((n) => (
        <TreeItem
          key={n.path}
          node={n}
          repoId={repoId}
          activePath={activePath}
          router={router}
        />
      ))}
    </ul>
  );
}

type RouterLike = ReturnType<typeof useRouter>;

function TreeItem({
  node,
  repoId,
  activePath,
  router,
}: {
  node: TreeNode;
  repoId: string;
  activePath?: string;
  router: RouterLike;
}) {
  if (node.type === "dir") {
    return (
      <li>
        <details className="group">
          <summary className="list-none [&::-webkit-details-marker]:hidden cursor-pointer flex items-center py-0.5 px-1 hover:bg-muted whitespace-nowrap overflow-hidden text-ellipsis">
            <ChevronRight />
            <span className="overflow-hidden text-ellipsis">{node.name}/</span>
          </summary>
          <ul className="pl-4">
            {node.children?.map((c) => (
              <TreeItem
                key={c.path}
                node={c}
                repoId={repoId}
                activePath={activePath}
                router={router}
              />
            ))}
          </ul>
        </details>
      </li>
    );
  }

  const isActive = activePath === node.path;
  const pin = () => {
    window.dispatchEvent(
      new CustomEvent("pin-file", { detail: { path: node.path } }),
    );
  };
  return (
    <li>
      <button
        type="button"
        onClick={() => {
          const current = new URL(window.location.href).searchParams.get("file");
          if (current === node.path) {
            pin();
          } else {
            router.push(
              `/quiz/${repoId}?file=${encodeURIComponent(node.path)}`,
              { scroll: false },
            );
          }
        }}
        onDoubleClick={pin}
        className={`block w-full text-left cursor-pointer select-none py-0.5 px-1 pl-5 hover:bg-muted whitespace-nowrap overflow-hidden text-ellipsis ${
          isActive ? "bg-muted text-info-fg" : ""
        }`}
      >
        {node.name}
      </button>
    </li>
  );
}

function ChevronRight() {
  return (
    <svg
      className="w-3 h-3 mr-1 shrink-0 transition-transform group-open:rotate-90"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <polyline points="6 4 10 8 6 12" />
    </svg>
  );
}
