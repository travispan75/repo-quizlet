from pathlib import Path
from typing import ClassVar

from pipeline.models import File, Occurrence, Symbol
from pipeline.scip.proto.scip_pb2 import Index

from pipeline.context import Context
from pipeline.stages.base_stage import BaseStage
from pipeline.stages.index_repo import IndexRepo


class BuildScipBaseTables(BaseStage):
    depends_on: ClassVar[tuple[type["BaseStage"], ...]] = (IndexRepo,)

    def run(self, ctx: Context) -> None:
        if ctx.scip_artifacts_path is None:
            raise ValueError("SCIP artifacts path is missing from context")

        artifacts_path = Path(ctx.scip_artifacts_path)
        for scip_file in sorted(artifacts_path.glob("*.scip")):
            index = Index()
            index.ParseFromString(scip_file.read_bytes())
            ctx.scip_indexes[scip_file.stem] = index

        for index in ctx.scip_indexes.values():
            for document in index.documents:
                for symbol_info in document.symbols:
                    symbol = Symbol.from_symbol_information(symbol_info, document)
                    ctx.symbol_table[symbol.symbol_id] = symbol
                occurrences = Occurrence.from_document(document)
                for occurrence in occurrences:
                    ctx.occurrence_table[occurrence.occurrence_id] = occurrence
                file = File.from_document(document)
                ctx.file_table[file.file_path] = file
