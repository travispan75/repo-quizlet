import pickle
from pathlib import Path
from typing import ClassVar

from pipeline.context.models import File, Occurrence, Symbol
from pipeline.context.scip.proto.scip_pb2 import Index

from pipeline.context import State
from pipeline.core.base_stage import BaseStage
from pipeline.context.stages.index_repo import IndexRepo


_CACHE_DIR = Path(__file__).resolve().parents[1] / ".cache"
_CACHE_VERSION = 1


def _cache_path(cache_key: str, source_hash: str) -> Path:
    return _CACHE_DIR / cache_key / f"scip_v{_CACHE_VERSION}_{source_hash}.pkl"


class BuildScipBaseTables(BaseStage):
    depends_on: ClassVar[tuple[type["BaseStage"], ...]] = (IndexRepo,)

    def run(self, ctx: State) -> None:
        if ctx._scip_cache_hit:
            return

        if ctx.scip_artifacts_path is None:
            raise ValueError("SCIP artifacts path is missing from State")

        artifacts_path = Path(ctx.scip_artifacts_path)
        indexes: list[Index] = []
        for scip_file in sorted(artifacts_path.glob("*.scip")):
            index = Index()
            index.ParseFromString(scip_file.read_bytes())
            indexes.append(index)

        for index in indexes:
            for document in index.documents:
                for symbol_info in document.symbols:
                    symbol = Symbol.from_symbol_information(symbol_info, document)
                    ctx.symbol_table[symbol.symbol_id] = symbol
                occurrences = Occurrence.from_document(document)
                for occurrence in occurrences:
                    ctx.occurrence_table[occurrence.occurrence_id] = occurrence
                file = File.from_document(document)
                ctx.file_table[file.file_path] = file

        ctx.scip_indexes.clear()
        if ctx.scip_tempdir is not None:
            ctx.scip_tempdir.cleanup()
            ctx.scip_tempdir = None
        ctx.scip_artifacts_path = None

        if ctx._scip_source_hash is not None:
            cache_path = _cache_path(ctx.cache_key, ctx._scip_source_hash)
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(cache_path, "wb") as f:
                pickle.dump(
                    {
                        "symbol_table": ctx.symbol_table,
                        "occurrence_table": ctx.occurrence_table,
                        "file_table": ctx.file_table,
                    },
                    f,
                )
