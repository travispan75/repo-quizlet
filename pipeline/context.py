from collections import defaultdict
from typing import Any, DefaultDict
from tempfile import TemporaryDirectory

from pipeline.models import Chunk, File, Occurrence, Symbol


class Context:
    def __init__(
        self,
        repo_path: str,
        job_id: str | None = None,
        repo_name: str | None = None,
        repo_url: str | None = None,
    ):
        self.job_id = job_id
        self.repo_name = repo_name
        self.repo_path = repo_path
        self.repo_url = repo_url

        self.language_list: set[str] = set()

        self.scip_artifacts_path: str | None = None
        self.scip_tempdir: TemporaryDirectory[str] | None = None

        self.scip_indexes: dict[str, Any] = {}

        self.symbol_table: dict[str, Symbol] = {}
        self.occurrence_table: dict[str, Occurrence] = {}
        self.file_table: dict[str, File] = {}

        self.definition_map: DefaultDict[str, list[str]] = defaultdict(list)
        self.reference_map: DefaultDict[str, list[str]] = defaultdict(list)

        self.file_to_symbol_map: DefaultDict[str, set[str]] = defaultdict(set)
        self.symbol_to_file_map: DefaultDict[str, set[str]] = defaultdict(set)

        self.call_graph: DefaultDict[str, set[str]] = defaultdict(set)
        self.called_by_graph: DefaultDict[str, set[str]] = defaultdict(set)

        self.dependency_graph: DefaultDict[str, DefaultDict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )

        self.graph_clusters: list[dict[str, str]] = []

        self.chunks: list[Chunk] = []
