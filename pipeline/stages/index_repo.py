from pathlib import Path
from tempfile import TemporaryDirectory
from typing import ClassVar

from pipeline.context import Context
from pipeline.scip.scip_indexer_factory import get_scip_indexer
from pipeline.stages.base_stage import BaseStage
from pipeline.stages.parse_repo import ParseRepo


class IndexRepo(BaseStage):
    depends_on: ClassVar[tuple[type["BaseStage"], ...]] = (ParseRepo,)

    def run(self, ctx: Context) -> None:
        ctx.scip_tempdir = TemporaryDirectory()
        ctx.scip_artifacts_path = ctx.scip_tempdir.name

        for language in ctx.language_list:
            indexer = get_scip_indexer(language)
            output_path = (Path(ctx.scip_artifacts_path) / f"{language}.scip").as_posix()
            indexer.run(ctx.repo_path, ctx.repo_name, output_path)
            print(f"SCIP indexing succeeded for {language}")
