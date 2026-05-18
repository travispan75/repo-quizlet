from abc import ABC, abstractmethod
from typing import Any, ClassVar


class BaseStage(ABC):
    depends_on: ClassVar[tuple[type["BaseStage"], ...]] = ()

    @abstractmethod
    def run(self, ctx: Any) -> None:
        pass
