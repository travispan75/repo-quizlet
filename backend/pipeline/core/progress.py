from __future__ import annotations

from abc import ABC, abstractmethod


class ProgressReporter(ABC):
    """Reports pipeline progress to an external observer.

    Stage transitions are signalled by `stage(name, index, total)` immediately
    BEFORE that stage runs; there is no separate `stage_finished` event because
    "stage N+1 started" implies "stage N done". `heartbeat` is used inside
    long-running stages (parallel LLM loops) to report sub-progress within the
    current stage. `done` / `failed` are top-level signals emitted by the
    worker after all pipelines complete or one fails.
    """

    @abstractmethod
    def stage(self, name: str, index: int, total: int) -> None: ...

    @abstractmethod
    def heartbeat(self, done: int, total: int) -> None: ...

    @abstractmethod
    def done(self) -> None: ...

    @abstractmethod
    def failed(self, error: str) -> None: ...

    def mark_repo_updated(self, updated: bool) -> None:
        """Optional hook: CloneRepo announces whether the pull brought new
        commits, so the UI can show a "pulled latest" banner. Default no-op."""
        return


class NoopReporter(ProgressReporter):
    def stage(self, name: str, index: int, total: int) -> None:
        return

    def heartbeat(self, done: int, total: int) -> None:
        return

    def done(self) -> None:
        return

    def failed(self, error: str) -> None:
        return
