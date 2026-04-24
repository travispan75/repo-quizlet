import os
from typing import ClassVar

from pipeline.context import Context
from pipeline.models import Chunk
from pipeline.stages.base_stage import BaseStage
from pipeline.stages.build_call_graph import BuildCallGraph
from pipeline.stages.build_symbol_occurrence_maps import BuildSymbolOccurrenceMaps


_CHUNK_KINDS = frozenset({
    "Class",
    "Function",
    "Method",
})


class BuildChunks(BaseStage):
    depends_on: ClassVar[tuple[type["BaseStage"], ...]] = (BuildCallGraph,)

    def run(self, ctx: Context) -> None:
        for symbol_id, occurrence_ids in ctx.definition_map.items():
            symbol = ctx.symbol_table.get(symbol_id)
            if symbol is None or symbol.kind not in _CHUNK_KINDS:
                continue

            for occurrence_id in occurrence_ids:
                occurrence = ctx.occurrence_table.get(occurrence_id)
                if occurrence is None:
                    continue

                abs_path = os.path.join(ctx.repo_path, occurrence.file_path)
                try:
                    with open(abs_path, encoding="utf-8", errors="replace") as f:
                        lines = f.readlines()
                except OSError:
                    continue

                start = occurrence.start_line
                end = occurrence.end_line
                code = "".join(lines[start : end + 1])

                ctx.chunks.append(
                    Chunk(
                        symbol_id=symbol_id,
                        name=symbol.display_name,
                        file=occurrence.file_path,
                        start_line=start,
                        end_line=end,
                        code=code,
                        calls=frozenset(ctx.call_graph.get(symbol_id, ())),
                        called_by=frozenset(ctx.called_by_graph.get(symbol_id, ())),
                    )
                )
