from typing import Any

from pipeline.core.dag_scheduler.executors.base_executor import BaseExecutor


class SequentialExecutor(BaseExecutor):
    def execute(self, ctx: Any) -> None:
        total = self.total_steps()
        i = 0
        for level in self.levels:
            for step in level:
                i += 1
                self.progress.stage(step.__name__, i, total)
                try:
                    step().run(ctx)
                except Exception as e:
                    raise RuntimeError(f"Pipeline failed in stage {step.__name__}: {e}") from e
