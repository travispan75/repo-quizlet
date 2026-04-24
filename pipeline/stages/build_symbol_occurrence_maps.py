from collections import defaultdict
from typing import ClassVar

from pipeline.context import Context
from pipeline.stages.base_stage import BaseStage
from pipeline.stages.build_scip_base_tables import BuildScipBaseTables


class BuildSymbolOccurrenceMaps(BaseStage):
    depends_on: ClassVar[tuple[type["BaseStage"], ...]] = (BuildScipBaseTables,)

    def run(self, ctx: Context) -> None:
        for occurrence_id, occurrence in ctx.occurrence_table.items():
            if occurrence.is_definition:
                ctx.definition_map[occurrence.symbol_id].append(occurrence_id)

            if occurrence.is_reference:
                ctx.reference_map[occurrence.symbol_id].append(occurrence_id)
