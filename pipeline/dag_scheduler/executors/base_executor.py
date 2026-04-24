from abc import ABC, abstractmethod

from pipeline.context import Context
from pipeline.stages.base_stage import BaseStage


class BaseExecutor(ABC):
    def __init__(self, steps: list[type[BaseStage]] | None = None):
        self.steps = steps or []

    @abstractmethod
    def execute(self, ctx: Context) -> None:
        pass
