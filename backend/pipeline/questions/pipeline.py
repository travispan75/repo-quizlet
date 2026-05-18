from pathlib import Path

from pipeline.core import Pipeline
from pipeline.questions.stages import (
    GenerateConceptQuestions,
    GenerateHypotheticals,
    GenerateQuestions,
    PersistQuestions,
)
from pipeline.questions.state import QuestionState


class QuestionPipeline(Pipeline):
    steps = (
        GenerateQuestions,
        GenerateHypotheticals,
        GenerateConceptQuestions,
        PersistQuestions,
    )

    def run(self, db_path: str | Path) -> QuestionState:
        ctx = QuestionState(db_path=db_path, progress=self.progress)
        self.executor.levels = self.scheduler.schedule(list(self.steps))
        self.executor.execute(ctx)
        return ctx
