from pipeline.context.stages.cluster_graphs import ClusterGraphs


def test_cluster_graphs_produces_layers(ctx_factory):
    ctx = ctx_factory(ClusterGraphs)
    ClusterGraphs().run(ctx)
    assert ctx.graph_clusters
    assert all(layer for layer in ctx.graph_clusters)
    for layer in ctx.graph_clusters:
        for cluster in layer.values():
            assert cluster.files
