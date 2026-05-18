from pipeline.context.stages.build_call_graph import BuildCallGraph


def test_build_call_graph_populates_symbols(ctx_factory):
    ctx = ctx_factory(BuildCallGraph)
    BuildCallGraph().run(ctx)
    assert any(s.calls for s in ctx.symbol_table.values())
    assert any(s.called_by for s in ctx.symbol_table.values())
