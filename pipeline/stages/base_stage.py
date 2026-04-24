from abc import ABC, abstractmethod
from typing import ClassVar

from pipeline.context import Context

class BaseStage(ABC):
    depends_on: ClassVar[tuple[type["BaseStage"], ...]] = ()

    @abstractmethod
    def run(self, ctx: Context) -> None:
        pass
