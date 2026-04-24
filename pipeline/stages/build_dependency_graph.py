from collections import defaultdict
from typing import ClassVar

from pipeline.context import Context
from pipeline.stages.base_stage import BaseStage
from pipeline.stages.build_file_symbol_maps import BuildFileSymbolMaps
from pipeline.stages.build_symbol_occurrence_maps import BuildSymbolOccurrenceMaps


class BuildDependencyGraph(BaseStage):
    depends_on: ClassVar[tuple[type["BaseStage"], ...]] = (
        BuildSymbolOccurrenceMaps,
        BuildFileSymbolMaps,
    )

    def run(self, ctx: Context) -> None:
        for occurrence in ctx.occurrence_table.values():
            source_file = ctx.file_table[occurrence.file_path].file_path

            for definition_occurrence_id in ctx.definition_map[occurrence.symbol_id]:
                definition_occurrence = ctx.occurrence_table[definition_occurrence_id]
                target_file = ctx.file_table[definition_occurrence.file_path].file_path

                if source_file != target_file:
                    ctx.dependency_graph[source_file][target_file] += 1
                    ctx.dependency_graph[target_file][source_file] += 1
