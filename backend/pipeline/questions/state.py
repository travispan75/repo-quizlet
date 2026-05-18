from pathlib import Path

from pipeline.core.progress import NoopReporter, ProgressReporter
from pipeline.questions.db import RepoDB
from pipeline.questions.models.pipeline_models import Problem


class QuestionState:
    def __init__(
        self,
        db_path: str | Path,
        progress: ProgressReporter | None = None,
    ):
        self.db: RepoDB = RepoDB(db_path)
        self.problems: list[Problem] = []
        self.progress: ProgressReporter = progress or NoopReporter()
        repo = self.db.get_repo()
        if repo is None:
            raise RuntimeError(
                f"repo.db at {db_path} has no repo row; cannot run pipeline"
            )
        self.cache_key: str = repo.id
