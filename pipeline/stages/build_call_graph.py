from typing import ClassVar

from pipeline.context import Context
from pipeline.stages.base_stage import BaseStage
from pipeline.stages.build_symbol_occurrence_maps import BuildSymbolOccurrenceMaps


class BuildCallGraph(BaseStage):
    depends_on: ClassVar[tuple[type["BaseStage"], ...]] = (BuildSymbolOccurrenceMaps,)

    def run(self, ctx: Context) -> None:
        for occurrence in ctx.occurrence_table.values():
            if not occurrence.is_reference or not occurrence.enclosing_symbol_id:
                continue

            caller = occurrence.enclosing_symbol_id
            callee = occurrence.symbol_id

            if caller == callee:
                continue

            ctx.call_graph[caller].add(callee)
            ctx.called_by_graph[callee].add(caller)
