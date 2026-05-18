from collections import defaultdict
from typing import ClassVar

import community as community_louvain
import networkx as nx

from pipeline.context import State
from pipeline.context.models import Cluster
from pipeline.core.base_stage import BaseStage
from pipeline.context.stages.build_dependency_graph import BuildDependencyGraph


_NUM_RUNS = 3
_MAX_LEVELS = 5
_RANDOM_STATE: int | None = None


class ClusterGraphs(BaseStage):
    depends_on: ClassVar[tuple[type["BaseStage"], ...]] = (BuildDependencyGraph,)

    def run(self, ctx: State) -> None:
        graph = _build_graph(ctx)
        if not graph:
            return

        dendrogram = _best_dendrogram(graph)
        levels = _cap_levels(list(range(len(dendrogram))), _MAX_LEVELS)
        print(
            f"[cluster_graphs] dendrogram_levels={len(dendrogram)} "
            f"kept_levels={levels} "
            f"per_level_communities="
            + str([
                len(set(community_louvain.partition_at_level(dendrogram, i).values()))
                for i in range(len(dendrogram))
            ]),
            flush=True,
        )
        ctx.graph_clusters = _build_clusters(dendrogram, levels)


def _build_graph(ctx: State) -> nx.Graph:
    graph = nx.Graph()
    graph.add_nodes_from(ctx.dependency_graph.keys())
    for source, neighbours in ctx.dependency_graph.items():
        for target, weight in neighbours.items():
            if source <= target:
                graph.add_edge(source, target, weight=weight)
    return graph


def _best_dendrogram(graph: nx.Graph) -> list[dict[str, int]]:
    best_dendrogram: list[dict[str, int]] | None = None
    best_score = float("-inf")
    for i in range(_NUM_RUNS):
        random_state = None if _RANDOM_STATE is None else _RANDOM_STATE + i
        dendrogram = community_louvain.generate_dendrogram(
            graph, weight="weight", random_state=random_state
        )
        top = community_louvain.partition_at_level(dendrogram, len(dendrogram) - 1)
        score = community_louvain.modularity(top, graph, weight="weight")
        if score > best_score:
            best_score = score
            best_dendrogram = dendrogram
    assert best_dendrogram is not None
    return best_dendrogram


def _cap_levels(levels: list[int], cap: int) -> list[int]:
    if len(levels) <= cap:
        return levels
    last_idx = len(levels) - 1
    indices = sorted({round(i * last_idx / (cap - 1)) for i in range(cap)})
    return [levels[i] for i in indices]


def _build_clusters(
    dendrogram: list[dict[str, int]],
    levels: list[int],
) -> list[dict[str, Cluster]]:
    layers: list[dict[str, Cluster]] = []
    for level in levels:
        partition = community_louvain.partition_at_level(dendrogram, level)

        files_by_community: defaultdict[int, set[str]] = defaultdict(set)
        for file_path, community in partition.items():
            files_by_community[community].add(file_path)

        layer: dict[str, Cluster] = {}
        for community, files in files_by_community.items():
            cluster_id = f"L{level}_{community}"
            layer[cluster_id] = Cluster(
                cluster_id=cluster_id,
                files=frozenset(files),
            )
        layers.append(layer)
    return layers
