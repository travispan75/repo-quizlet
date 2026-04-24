import random
import unittest
from collections import defaultdict

import networkx as nx

from pipeline.context import Context
from pipeline.stages.cluster_graphs import ClusterGraphs


def _communities_from_partition(partition: dict[str, str]) -> list[set[str]]:
    communities = defaultdict(set)
    for node, community in partition.items():
        communities[community].add(node)
    return list(communities.values())


class TestClusterGraphs(unittest.TestCase):
    def test_louvain_runs_on_karate_club_graph(self) -> None:
        random.seed(0)

        karate_graph = nx.karate_club_graph()
        ctx = Context(repo_path=".")

        for source, target in karate_graph.edges():
            source_node = str(source)
            target_node = str(target)
            ctx.dependency_graph[source_node][target_node] += 1
            ctx.dependency_graph[target_node][source_node] += 1

        ClusterGraphs().run(ctx)

        self.assertTrue(ctx.graph_clusters)

        final_partition = ctx.graph_clusters[-1]
        expected_nodes = {str(node) for node in karate_graph.nodes()}
        self.assertEqual(set(final_partition.keys()), expected_nodes)

        communities = _communities_from_partition(final_partition)
        self.assertGreater(len(communities), 1)

        scored_graph = nx.Graph()
        scored_graph.add_nodes_from(expected_nodes)
        for source, neighbours in ctx.dependency_graph.items():
            for target, weight in neighbours.items():
                if source <= target:
                    scored_graph.add_edge(source, target, weight=weight)

        score = nx.algorithms.community.quality.modularity(
            scored_graph,
            communities,
            weight="weight",
        )
        self.assertGreater(score, 0.0)


if __name__ == "__main__":
    unittest.main()
