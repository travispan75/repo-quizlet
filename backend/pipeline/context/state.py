import hashlib
from collections import defaultdict
from typing import Any, DefaultDict
from tempfile import TemporaryDirectory

from pipeline.context.models import Cluster, ConceptGroup, File, Occurrence, Symbol
from pipeline.core.progress import NoopReporter, ProgressReporter


class State:
    def __init__(
        self,
        repo_path: str,
        job_id: str | None = None,
        repo_name: str | None = None,
        repo_url: str | None = None,
        progress: ProgressReporter | None = None,
    ):
        # ---- constructor inputs ----
        self.job_id = job_id
        self.repo_name = repo_name
        self.repo_path = repo_path
        self.repo_url = repo_url
        self.progress: ProgressReporter = progress or NoopReporter()
        # Cache key for partitioning per-repo cache files. Prefer the upstream
        # job_id (sha1 of git_repo_url); fall back to a hash of repo_path so
        # CLI runs without a job_id still get an isolated cache namespace.
        self.cache_key = job_id or hashlib.sha1(
            repo_path.encode("utf-8")
        ).hexdigest()

        # ---- CloneRepo ----
        self.source_changed: bool = False

        # ---- ParseRepo ----
        self.language_list: set[str] = set()
        self.readme: str | None = None

        # ---- BuildFileTree ----
        self.file_tree: str = ""

        # ---- IndexRepo ----
        self.scip_artifacts_path: str | None = None
        self.scip_tempdir: TemporaryDirectory[str] | None = None
        self.scip_indexes: dict[str, Any] = {}
        self._scip_source_hash: str | None = None
        self._scip_cache_hit: bool = False

        # ---- BuildScipBaseTables ----
        self.symbol_table: dict[str, Symbol] = {}
        self.occurrence_table: dict[str, Occurrence] = {}
        self.file_table: dict[str, File] = {}

        # ---- BuildSymbolOccurrenceMaps ----
        self.definition_map: DefaultDict[str, list[str]] = defaultdict(list)
        self.reference_map: DefaultDict[str, list[str]] = defaultdict(list)

        # ---- BuildFileSymbolMaps ----
        self.file_to_symbol_map: DefaultDict[str, set[str]] = defaultdict(set)
        self.symbol_to_file_map: DefaultDict[str, set[str]] = defaultdict(set)

        # ---- BuildCallGraph ----
        self.call_graph: DefaultDict[str, set[str]] = defaultdict(set)
        self.called_by_graph: DefaultDict[str, set[str]] = defaultdict(set)

        # ---- BuildDependencyGraph ----
        self.dependency_graph: DefaultDict[str, DefaultDict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )

        # ---- ClusterGraphs ----
        self.graph_clusters: list[dict[str, Cluster]] = []

        # ---- BuildConceptGroups ----
        self.concept_groups: list[ConceptGroup] = []

        # ---- SummarizeRepo ----
        self.repo_summary: str | None = None

        # ---- EmbedSummaries ----
        self.repo_embedding: list[float] | None = None
