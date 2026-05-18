from pipeline.context.stages.summarize_clusters import SummarizeClusters


def test_summarize_clusters_populates_summaries(ctx_factory):
    ctx = ctx_factory(SummarizeClusters)
    SummarizeClusters().run(ctx)
    assert len(ctx.graph_clusters) > 0
    assert all(
        cluster.summary is not None
        for layer in ctx.graph_clusters
        for cluster in layer.values()
    )
