from typing import ClassVar

from pipeline.context import State
from pipeline.core.base_stage import BaseStage
from pipeline.context.stages.index_repo import IndexRepo


class BuildFileSymbolMaps(BaseStage):
    depends_on: ClassVar[tuple[type["BaseStage"], ...]] = (IndexRepo,)

    def run(self, ctx: State) -> None:
        for occurrence in ctx.occurrence_table.values():
            ctx.file_to_symbol_map[occurrence.file_path].add(occurrence.symbol_id)
            ctx.symbol_to_file_map[occurrence.symbol_id].add(occurrence.file_path)
