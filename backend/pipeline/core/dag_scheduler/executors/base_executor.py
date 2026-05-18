from abc import ABC, abstractmethod
from typing import Any

from pipeline.core.base_stage import BaseStage
from pipeline.core.progress import NoopReporter, ProgressReporter


class BaseExecutor(ABC):
    def __init__(
        self,
        levels: list[list[type[BaseStage]]] | None = None,
        progress: ProgressReporter | None = None,
    ):
        self.levels: list[list[type[BaseStage]]] = levels or []
        self.progress: ProgressReporter = progress or NoopReporter()

    @abstractmethod
    def execute(self, ctx: Any) -> None:
        pass

    def total_steps(self) -> int:
        return sum(len(level) for level in self.levels)
