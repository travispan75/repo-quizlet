import hashlib
import pickle
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import ClassVar

from pipeline.context import State
from pipeline.context.scip.scip_indexer import ScipIndexer
from pipeline.core.base_stage import BaseStage
from pipeline.context.stages.parse_repo import ParseRepo
from pipeline.context.stages.prepare_repo_venv import PrepareRepoVenv


_CACHE_DIR = Path(__file__).resolve().parents[1] / ".cache"
_CACHE_VERSION = 1
_SKIP_DIRS = frozenset({
    ".git", "__pycache__", ".venv", "venv", "node_modules",
    ".pytest_cache", "dist", "build", ".idea", ".vscode",
    ".tox", ".mypy_cache", ".ruff_cache",
})


def _compute_source_hash(repo_path: str) -> str:
    root = Path(repo_path)
    hasher = hashlib.sha1()
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in _SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        rel = path.relative_to(root).as_posix()
        hasher.update(rel.encode("utf-8"))
        hasher.update(b"\0")
        try:
            hasher.update(path.read_bytes())
        except OSError:
            continue
        hasher.update(b"\0")
    return hasher.hexdigest()[:16]


def _cache_path(cache_key: str, source_hash: str) -> Path:
    return _CACHE_DIR / cache_key / f"scip_v{_CACHE_VERSION}_{source_hash}.pkl"


class IndexRepo(BaseStage):
    depends_on: ClassVar[tuple[type["BaseStage"], ...]] = (ParseRepo, PrepareRepoVenv)

    def run(self, ctx: State) -> None:
        source_hash = _compute_source_hash(ctx.repo_path)
        ctx._scip_source_hash = source_hash

        cache_path = _cache_path(ctx.cache_key, source_hash)
        if cache_path.exists():
            try:
                with open(cache_path, "rb") as f:
                    data = pickle.load(f)
                ctx.symbol_table = data["symbol_table"]
                ctx.occurrence_table = data["occurrence_table"]
                ctx.file_table = data["file_table"]
                ctx._scip_cache_hit = True
                return
            except (pickle.PickleError, EOFError, KeyError, OSError):
                pass

        ctx._scip_cache_hit = False
        ctx.scip_tempdir = TemporaryDirectory()
        ctx.scip_artifacts_path = ctx.scip_tempdir.name

        if "python" in ctx.language_list:
            indexer = ScipIndexer()
            output_path = (Path(ctx.scip_artifacts_path) / "python.scip").as_posix()
            indexer.run(ctx.repo_path, ctx.repo_name, output_path)
