from pipeline.context.stages.build_file_tree import BuildFileTree


def test_build_file_tree_populates(ctx_factory):
    ctx = ctx_factory(BuildFileTree)
    BuildFileTree().run(ctx)
    assert ctx.file_tree
    assert "/" in ctx.file_tree
    assert ".git/" not in ctx.file_tree
    assert "__pycache__" not in ctx.file_tree
