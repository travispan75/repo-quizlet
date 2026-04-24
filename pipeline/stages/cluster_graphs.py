from typing import ClassVar
import community as community_louvain
import networkx as nx

from pipeline.context import Context
from pipeline.stages.base_stage import BaseStage
from pipeline.stages.build_dependency_graph import BuildDependencyGraph


class ClusterGraphs(BaseStage):
    depends_on: ClassVar[tuple[type["BaseStage"], ...]] = (BuildDependencyGraph,)

    def run(self, ctx: Context) -> None:
        def modularity(partition, graph) -> float:
            return community_louvain.modularity(partition, graph, weight="weight")

        graph = nx.Graph()
        graph.add_nodes_from(ctx.dependency_graph.keys())

        for source, neighbours in ctx.dependency_graph.items():
            for target, weight in neighbours.items():
                if source <= target:
                    graph.add_edge(source, target, weight=weight)

        best_partition = {}
        best_modularity = float("-inf")

        for _ in range(3):
            partition = community_louvain.best_partition(
                graph,
                weight="weight",
            )
            score = modularity(partition, graph)
            if score > best_modularity:
                best_modularity = score
                best_partition = {node: str(community) for node, community in partition.items()}

        ctx.graph_clusters = [best_partition]
