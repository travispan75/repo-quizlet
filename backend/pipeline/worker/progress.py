from __future__ import annotations

import threading
import time

from pipeline.core.progress import ProgressReporter
from pipeline.worker.redis_client import RedisClient


_PROGRESS_TTL_SECONDS = 60 * 60

_LABELS: dict[str, str] = {
    "CloneRepo":                "Cloning repo",
    "ParseRepo":                "Parsing repo",
    "BuildFileTree":            "Building file tree",
    "PrepareRepoVenv":          "Installing repo dependencies",
    "IndexRepo":                "SCIP indexing",
    "BuildScipBaseTables":      "Loading SCIP index",
    "BuildSymbolOccurrenceMaps": "Mapping symbol occurrences",
    "BuildFileSymbolMaps":      "Mapping files to symbols",
    "BuildCallGraph":           "Building call graph",
    "BuildDependencyGraph":     "Building dependency graph",
    "ClusterGraphs":            "Clustering",
    "BuildClusterSubgraphs":    "Building cluster subgraphs",
    "SummarizeFiles":           "Summarizing files",
    "BuildConceptGroups":       "Building concept groups",
    "SummarizeClusters":        "Summarizing clusters",
    "TitleClusters":            "Titling clusters",
    "SummarizeRepo":            "Summarizing repo",
    "PersistContext":           "Persisting context",
    "GenerateQuestions":        "Generating questions",
    "GenerateHypotheticals":    "Generating hypotheticals",
    "GenerateConceptQuestions": "Generating concept questions",
    "PersistQuestions":         "Persisting questions",
}


class RedisProgressReporter(ProgressReporter):
    def __init__(self, client: RedisClient, repo_id: str, repo_updated: bool = False):
        self._client = client
        self._key = f"progress:{repo_id}"
        self._pipeline = ""
        self._stage_name = ""
        self._stage_label = ""
        self._stage_index = 0
        self._stage_total = 0
        self._sub_done = 0
        self._sub_total = 0
        self._repo_updated = repo_updated
        self._lock = threading.Lock()

    def set_pipeline(self, pipeline: str) -> None:
        with self._lock:
            self._pipeline = pipeline

    def stage(self, name: str, index: int, total: int) -> None:
        with self._lock:
            self._stage_name = name
            self._stage_label = _LABELS.get(name, name)
            self._stage_index = index
            self._stage_total = total
            self._sub_done = 0
            self._sub_total = 0
            self._publish("running")

    def heartbeat(self, done: int, total: int) -> None:
        with self._lock:
            self._sub_done = done
            self._sub_total = total
            self._publish("running")

    def done(self) -> None:
        with self._lock:
            self._publish("done")

    def failed(self, error: str) -> None:
        with self._lock:
            self._publish("failed", error=error)

    def mark_repo_updated(self, updated: bool) -> None:
        with self._lock:
            self._repo_updated = updated
            self._publish("running")

    def _publish(self, status: str, error: str | None = None) -> None:
        payload: dict = {
            "status": status,
            "pipeline": self._pipeline,
            "stage": self._stage_name,
            "stage_label": self._stage_label,
            "stage_index": self._stage_index,
            "stage_total": self._stage_total,
            "sub_done": self._sub_done,
            "sub_total": self._sub_total,
            "repo_updated": self._repo_updated,
            "updated_at": time.time(),
        }
        if error is not None:
            payload["error"] = error
        try:
            self._client.set_json(self._key, payload, ex=_PROGRESS_TTL_SECONDS)
        except Exception as e:
            print(f"[progress] failed to publish: {e}")
