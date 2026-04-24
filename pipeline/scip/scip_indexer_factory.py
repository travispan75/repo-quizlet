from pipeline.scip.scip_indexer import ScipIndexer
from pipeline.scip.scip_python import ScipPythonIndexer
from pipeline.scip.scip_typescript import ScipTypescriptIndexer

_INDEXERS: dict[str, ScipIndexer] = {
    "python": ScipPythonIndexer(),
    "typescript": ScipTypescriptIndexer(),
    "javascript": ScipTypescriptIndexer(),
    "tsx": ScipTypescriptIndexer(),
}


def get_scip_indexer(language: str) -> ScipIndexer:
    indexer = _INDEXERS.get(language)
    if indexer is None:
        raise ValueError(f"No SCIP indexer registered for language: {language!r}")
    return indexer
