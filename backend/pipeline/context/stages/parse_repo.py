import os
from pathlib import Path
from typing import ClassVar

from pipeline.context import State
from pipeline.context.stages.clone_repo import CloneRepo
from pipeline.core.base_stage import BaseStage

LANGUAGE_BY_EXTENSION: dict[str, str] = {
    "py": "python",
    "js": "javascript",
    "mjs": "javascript",
    "cjs": "javascript",
    "ts": "typescript",
    "mts": "typescript",
    "cts": "typescript",
    "tsx": "tsx",
}

_README_CANDIDATES = [
    "README.md",
    "README.rst",
    "README.txt",
    "README",
    "readme.md",
    "readme.rst",
    "readme.txt",
    "readme",
]


def _read_readme(repo_path: str) -> str | None:
    base = Path(repo_path)
    if not base.exists() or not base.is_dir():
        return None
    for name in _README_CANDIDATES:
        path = base / name
        if path.is_file():
            try:
                return path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                return None
    return None


class ParseRepo(BaseStage):
    depends_on: ClassVar[tuple[type["BaseStage"], ...]] = (CloneRepo,)

    def run(self, ctx: State) -> None:
        repo_path = ctx.repo_path

        for root, dirs, files in os.walk(repo_path):
            for file in files:
                ext = file.split('.')[-1]
                if ext in LANGUAGE_BY_EXTENSION:
                    ctx.language_list.add(LANGUAGE_BY_EXTENSION[ext])

        ctx.readme = _read_readme(repo_path)
