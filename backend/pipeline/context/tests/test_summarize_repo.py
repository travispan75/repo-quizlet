from pipeline.context.stages.summarize_repo import SummarizeRepo


def test_summarize_repo_populates_summary(ctx_factory):
    ctx = ctx_factory(SummarizeRepo)
    SummarizeRepo().run(ctx)
    assert ctx.repo_summary is not None
    assert ctx.repo_summary.strip() != ""
