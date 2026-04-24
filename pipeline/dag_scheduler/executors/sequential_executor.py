from pipeline.context import Context
from pipeline.dag_scheduler.executors.base_executor import BaseExecutor


class SequentialExecutor(BaseExecutor):
    def execute(self, ctx: Context) -> None:
        for step in self.steps:
            try:
                step().run(ctx)
            except Exception as e:
                raise RuntimeError(f"Pipeline failed in stage {step.__name__}: {e}") from e
