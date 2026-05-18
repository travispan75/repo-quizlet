import dataclasses
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import ClassVar

from tqdm import tqdm

from pipeline.context import State
from pipeline.context.models import Cluster
from pipeline.core.llm import OpenAIClient
from pipeline.core.base_stage import BaseStage
from pipeline.context.stages.build_cluster_subgraphs import BuildClusterSubgraphs
from pipeline.context.stages.cluster_graphs import ClusterGraphs


_MAX_WORKERS = 16
_PROMPT_TOKEN_BUDGET = 6000
_CACHE_DIR = Path(__file__).resolve().parents[1] / ".cache"
_CACHE_NAME = "cluster_summaries.json"

_FILES_PROMPT = """Below are the source files belonging to one cluster (a tightly-coupled group of files in a codebase). Each file is shown with its path and full contents.

Write a 3-5 sentence summary describing the cluster's cohesive role and purpose in the codebase. SYNTHESIZE - capture the overall theme and responsibility of this group of files. Do NOT enumerate the files one by one; do not say "the code includes X, Y, and Z" - describe the unifying purpose.

Output rules:
- Do not start with "this cluster", "this group", "this module", "this set", "this code", or "these files".
- Lead with an action-oriented description (e.g., "Manages...", "Implements...", "Provides...").
- Output flowing prose only - no bullet points, no markdown, no headings.

FILES:
{units}

CLUSTER SUMMARY:"""

_SUBCLUSTER_PROMPT = """Below are summaries of sub-clusters that together form one larger cluster (a coarse-grained grouping in a codebase).

Write a 3-5 sentence summary describing the larger cluster's cohesive role and purpose in the codebase. SYNTHESIZE - capture the overall theme this group represents. Do NOT enumerate the sub-clusters one by one - describe the unifying purpose.

Output rules:
- Do not start with "this cluster", "this group", "this module", "this set", or "this code".
- Lead with an action-oriented description (e.g., "Manages...", "Implements...", "Provides...").
- Output flowing prose only - no bullet points, no markdown, no headings.

SUB-CLUSTER SUMMARIES:
{units}

CLUSTER SUMMARY:"""

_PARTIAL_PROMPT = """Below are inputs from a portion of a larger cluster. Your output will later be combined with other portions to produce the full cluster summary.

Write a 2-4 sentence synthesis. SYNTHESIZE - do not enumerate the inputs one by one.

Output rules:
- Do not write linking phrases such as "additionally", "moreover", "furthermore", "in summary", or "overall" - your output is a fragment, not a standalone conclusion.
- Do not start with "this slice", "this portion", "this group", "this module", or "this code".
- Output flowing prose only - no bullet points, no markdown, no headings.

INPUTS:
{units}

SYNTHESIS:"""


class SummarizeClusters(BaseStage):
    depends_on: ClassVar[tuple[type["BaseStage"], ...]] = (
        ClusterGraphs,
        BuildClusterSubgraphs,
    )

    def run(self, ctx: State) -> None:
        if not ctx.graph_clusters:
            return

        repo_root = Path(ctx.repo_path)
        client = OpenAIClient()
        cache = _load_cache(ctx.cache_key)
        used_hashes: set[str] = set()

        for layer_idx, layer in enumerate(ctx.graph_clusters):
            inputs_by_cluster = self._build_inputs(
                ctx, layer_idx, layer, repo_root,
            )

            kept = {
                cid: cluster
                for cid, cluster in layer.items()
                if cid in inputs_by_cluster
            }
            if not kept:
                ctx.graph_clusters[layer_idx] = {}
                continue

            prompt = _FILES_PROMPT if layer_idx == 0 else _SUBCLUSTER_PROMPT

            cluster_hashes = {
                cid: _hash_entries(inputs_by_cluster[cid]) for cid in kept
            }
            used_hashes.update(cluster_hashes.values())
            pending = [cid for cid, h in cluster_hashes.items() if h not in cache]

            if pending:
                with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as ex:
                    futures = {
                        ex.submit(
                            _summarize_cluster,
                            client,
                            inputs_by_cluster[cid],
                            prompt,
                        ): cid
                        for cid in pending
                    }
                    total = len(futures)
                    for i, fut in enumerate(
                        tqdm(
                            as_completed(futures),
                            total=total,
                            desc=f"summarize clusters L{layer_idx}",
                        ),
                        start=1,
                    ):
                        cid = futures[fut]
                        cache[cluster_hashes[cid]] = fut.result()
                        ctx.progress.heartbeat(i, total)

            for cluster_id in list(kept):
                kept[cluster_id] = dataclasses.replace(
                    kept[cluster_id],
                    summary=cache[cluster_hashes[cluster_id]],
                )
            ctx.graph_clusters[layer_idx] = kept

        ctx.graph_clusters = [layer for layer in ctx.graph_clusters if layer]
        cache = {h: v for h, v in cache.items() if h in used_hashes}
        _save_cache(cache, ctx.cache_key)

    def _build_inputs(
        self,
        ctx: State,
        layer_idx: int,
        layer: dict[str, Cluster],
        repo_root: Path,
    ) -> dict[str, list[tuple[str, str]]]:
        result: dict[str, list[tuple[str, str]]] = {}
        if layer_idx == 0:
            for cluster_id, cluster in layer.items():
                entries: list[tuple[str, str]] = []
                for file_path in sorted(cluster.files):
                    contents = _read_file(repo_root, file_path)
                    if contents is not None:
                        entries.append((file_path, contents))
                if entries:
                    result[cluster_id] = entries
        else:
            lower_layer = ctx.graph_clusters[layer_idx - 1]
            for cluster_id, cluster in layer.items():
                entries = [
                    (child_id, child.summary)
                    for child_id, child in lower_layer.items()
                    if child.summary is not None and child.files <= cluster.files
                ]
                entries.sort()
                if entries:
                    result[cluster_id] = entries
        return result


def _summarize_cluster(
    client: OpenAIClient,
    entries: list[tuple[str, str]],
    full_prompt: str,
) -> str:
    while True:
        formatted = _format_entries(entries)
        if _approx_tokens(formatted) <= _PROMPT_TOKEN_BUDGET:
            return client.generate(full_prompt.format(units=formatted))

        batches = _pack_entries(entries, _PROMPT_TOKEN_BUDGET)
        if len(batches) == 1:
            return client.generate(
                full_prompt.format(units=_format_entries(batches[0]))
            )

        partials = [
            client.generate(_PARTIAL_PROMPT.format(units=_format_entries(batch)))
            for batch in batches
        ]
        entries = [(f"partial_{i}", p) for i, p in enumerate(partials)]


def _read_file(repo_root: Path, relative_path: str) -> str | None:
    try:
        return (repo_root / relative_path).read_text(encoding="utf-8", errors="replace")
    except (OSError, ValueError):
        return None


def _format_entries(entries: list[tuple[str, str]]) -> str:
    return "\n\n".join(f"=== {label} ===\n{body}" for label, body in entries)


def _pack_entries(
    entries: list[tuple[str, str]],
    budget: int,
) -> list[list[tuple[str, str]]]:
    batches: list[list[tuple[str, str]]] = []
    current: list[tuple[str, str]] = []
    current_tokens = 0
    for entry in entries:
        n = _approx_tokens(entry[1])
        if current and current_tokens + n > budget:
            batches.append(current)
            current = []
            current_tokens = 0
        current.append(entry)
        current_tokens += n
    if current:
        batches.append(current)
    return batches


def _approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _hash_entries(entries: list[tuple[str, str]]) -> str:
    canonical = "\n".join(f"{label}\n{body}" for label, body in sorted(entries))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _cache_path(cache_key: str) -> Path:
    return _CACHE_DIR / cache_key / _CACHE_NAME


def _load_cache(cache_key: str) -> dict[str, str]:
    path = _cache_path(cache_key)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _save_cache(cache: dict[str, str], cache_key: str) -> None:
    path = _cache_path(cache_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, indent=2), encoding="utf-8")
