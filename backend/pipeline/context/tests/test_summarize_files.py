from pipeline.context.stages.summarize_files import SummarizeFiles


def test_summarize_files_populates_summaries(ctx_factory):
    ctx = ctx_factory(SummarizeFiles)
    SummarizeFiles().run(ctx)
    assert ctx.file_table
    assert all(f.summary for f in ctx.file_table.values())
