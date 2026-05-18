from abc import ABC, abstractmethod
from typing import Any

from pipeline.core.dag_scheduler import DagScheduler
from pipeline.core.dag_scheduler.executors import BaseExecutor, ParallelExecutor
from pipeline.core.progress import NoopReporter, ProgressReporter


class Pipeline(ABC):
    def __init__(
        self,
        scheduler: DagScheduler | None = None,
        executor: BaseExecutor | None = None,
        progress: ProgressReporter | None = None,
    ) -> None:
        self.scheduler = scheduler or DagScheduler()
        self.executor = executor or ParallelExecutor()
        self.progress: ProgressReporter = progress or NoopReporter()
        self.executor.progress = self.progress

    @abstractmethod
    def run(self, *args: Any, **kwargs: Any) -> Any:
        pass
