from pipeline.context import Context
from pipeline.dag_scheduler.executors.base_executor import BaseExecutor


class ParallelExecutor(BaseExecutor):
    def execute(self, ctx: Context) -> None:
        pass
