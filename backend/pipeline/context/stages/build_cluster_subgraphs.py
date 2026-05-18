import dataclasses
from collections import defaultdict
from typing import ClassVar

from pipeline.context import State
from pipeline.core.base_stage import BaseStage
from pipeline.context.stages.build_call_graph import BuildCallGraph
from pipeline.context.stages.cluster_graphs import ClusterGraphs


_SYMBOL_KINDS = {"Function", "Method", "Class"}


class BuildClusterSubgraphs(BaseStage):
    depends_on: ClassVar[tuple[type["BaseStage"], ...]] = (ClusterGraphs, BuildCallGraph)

    def run(self, ctx: State) -> None:
        if not ctx.graph_clusters:
            return

        for level, layer in enumerate(ctx.graph_clusters):
            for cluster_id, cluster in list(layer.items()):
                if level == 0:
                    subgraph = self._symbol_subgraph(ctx, cluster)
                elif level == 1:
                    subgraph = self._file_subgraph(ctx, cluster)
                else:
                    subgraph = self._contracted_subgraph(
                        ctx, cluster, ctx.graph_clusters[level - 1]
                    )
                layer[cluster_id] = dataclasses.replace(cluster, subgraph=subgraph)

    def _symbol_subgraph(self, ctx: State, cluster) -> dict[str, dict[str, int]]:
        symbols_in_cluster: set[str] = set()
        for file_path in cluster.files:
            symbols_in_cluster |= ctx.file_to_symbol_map.get(file_path, set())

        interesting = {
            sid
            for sid in symbols_in_cluster
            if (sym := ctx.symbol_table.get(sid)) is not None and sym.kind in _SYMBOL_KINDS
        }

        return {
            sid: {nid: 1 for nid in (ctx.symbol_table[sid].calls & interesting)}
            for sid in interesting
        }

    def _file_subgraph(self, ctx: State, cluster) -> dict[str, dict[str, int]]:
        files = cluster.files
        return {
            f: {
                neighbour: int(weight)
                for neighbour, weight in ctx.dependency_graph.get(f, {}).items()
                if neighbour in files
            }
            for f in files
        }

    def _contracted_subgraph(
        self,
        ctx: State,
        cluster,
        children_layer: dict,
    ) -> dict[str, dict[str, int]]:
        children = [c for c in children_layer.values() if c.files <= cluster.files]

        subgraph: dict[str, dict[str, int]] = {}
        for child_a in children:
            edges: defaultdict[str, int] = defaultdict(int)
            for child_b in children:
                if child_a is child_b:
                    continue
                weight = sum(
                    ctx.dependency_graph.get(f1, {}).get(f2, 0)
                    for f1 in child_a.files
                    for f2 in child_b.files
                )
                if weight > 0:
                    edges[child_b.cluster_id] = weight
            subgraph[child_a.cluster_id] = dict(edges)
        return subgraph
