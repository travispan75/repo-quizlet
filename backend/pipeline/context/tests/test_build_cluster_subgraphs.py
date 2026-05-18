from pipeline.context.stages.build_cluster_subgraphs import BuildClusterSubgraphs


def test_build_cluster_subgraphs_populates_subgraph(ctx_factory):
    ctx = ctx_factory(BuildClusterSubgraphs)
    BuildClusterSubgraphs().run(ctx)
    all_clusters = [c for layer in ctx.graph_clusters for c in layer.values()]
    assert all_clusters
    assert all(c.subgraph is not None for c in all_clusters)
    assert any(c.subgraph for c in all_clusters)
