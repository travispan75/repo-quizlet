import os
from typing import ClassVar

from pipeline.context import Context
from pipeline.stages.base_stage import BaseStage

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

class ParseRepo(BaseStage):
    depends_on: ClassVar[tuple[type["BaseStage"], ...]] = ()

    def run(self, ctx: Context) -> None:
        repo_path = ctx.repo_path

        for root, dirs, files in os.walk(repo_path):
            for file in files:
                ext = file.split('.')[-1]
                if ext in LANGUAGE_BY_EXTENSION:
                    ctx.language_list.add(LANGUAGE_BY_EXTENSION[ext])
