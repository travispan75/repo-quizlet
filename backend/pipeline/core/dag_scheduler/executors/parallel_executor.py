from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from typing import Any

from pipeline.core.dag_scheduler.executors.base_executor import BaseExecutor


class ParallelExecutor(BaseExecutor):
    def execute(self, ctx: Any) -> None:
        total = self.total_steps()
        completed = 0
        completed_lock = Lock()

        for level in self.levels:
            if not level:
                continue
            if len(level) == 1:
                step = level[0]
                with completed_lock:
                    completed += 1
                    idx = completed
                self.progress.stage(step.__name__, idx, total)
                try:
                    step().run(ctx)
                except Exception as e:
                    raise RuntimeError(
                        f"Pipeline failed in stage {step.__name__}: {e}"
                    ) from e
                continue

            errors: list[BaseException] = []
            with ThreadPoolExecutor(max_workers=len(level)) as ex:
                futures = {ex.submit(self._run_step, step, ctx): step for step in level}
                for fut in as_completed(futures):
                    step = futures[fut]
                    with completed_lock:
                        completed += 1
                        idx = completed
                    self.progress.stage(step.__name__, idx, total)
                    exc = fut.exception()
                    if exc is not None:
                        errors.append(
                            RuntimeError(
                                f"Pipeline failed in stage {step.__name__}: {exc}"
                            )
                        )
            if errors:
                raise errors[0]

    @staticmethod
    def _run_step(step, ctx) -> None:
        step().run(ctx)
