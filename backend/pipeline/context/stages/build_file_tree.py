from typing import ClassVar

import seedir as sd

from pipeline.context import State
from pipeline.context.stages.clone_repo import CloneRepo
from pipeline.core.base_stage import BaseStage


_EXCLUDE_FOLDERS = [
    ".git", "__pycache__", ".venv", "venv", "node_modules",
    ".pytest_cache", "dist", "build", ".idea", ".vscode",
    ".tox", ".mypy_cache", ".ruff_cache",
]


class BuildFileTree(BaseStage):
    depends_on: ClassVar[tuple[type["BaseStage"], ...]] = (CloneRepo,)

    def run(self, ctx: State) -> None:
        ctx.file_tree = sd.seedir(
            ctx.repo_path,
            printout=False,
            exclude_folders=_EXCLUDE_FOLDERS,
            sort=True,
        )
