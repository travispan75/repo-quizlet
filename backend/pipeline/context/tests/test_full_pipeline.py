def test_full_pipeline_runs(ctx_factory):
    ctx = ctx_factory()
    assert len(ctx.symbol_table) > 0
    assert len(ctx.occurrence_table) > 0
    assert len(ctx.file_table) > 0
    assert ctx.graph_clusters
    assert ctx.repo_summary is not None
    assert all(f.summary is not None for f in ctx.file_table.values())
    assert any(s.calls for s in ctx.symbol_table.values())
    assert any(c.subgraph for layer in ctx.graph_clusters for c in layer.values())
