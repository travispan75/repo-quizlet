from pipeline.dag_scheduler import DagScheduler
from pipeline.dag_scheduler.executors import SequentialExecutor
from pipeline.stages.build_call_graph import BuildCallGraph
from pipeline.stages.build_chunks import BuildChunks
from pipeline.stages.build_dependency_graph import BuildDependencyGraph
from pipeline.stages.build_file_symbol_maps import BuildFileSymbolMaps
from pipeline.stages.build_scip_base_tables import BuildScipBaseTables
from pipeline.stages.build_symbol_occurrence_maps import BuildSymbolOccurrenceMaps
from pipeline.stages.cluster_graphs import ClusterGraphs
from pipeline.stages.embed_chunks import EmbedChunks
from pipeline.context import Context
from pipeline.stages.index_repo import IndexRepo
from pipeline.stages.parse_repo import ParseRepo


class Pipeline:
    steps = (
        ParseRepo,
        IndexRepo,
        BuildScipBaseTables,
        BuildSymbolOccurrenceMaps,
        BuildFileSymbolMaps,
        BuildCallGraph,
        BuildDependencyGraph,
        ClusterGraphs,
        BuildChunks,
        EmbedChunks,
    )

    def __init__(self, scheduler=None, executor=None):
        self.scheduler = scheduler or DagScheduler()
        self.executor = executor or SequentialExecutor()

    def run(
        self,
        repo_path: str,
        job_id: str | None = None,
        repo_name: str | None = None,
        repo_url: str | None = None,
    ):
        ctx = Context(
            repo_path=repo_path,
            job_id=job_id,
            repo_name=repo_name,
            repo_url=repo_url,
        )
        scheduled_steps = self.scheduler.schedule(list(self.steps))
        self.executor.steps = [step for level in scheduled_steps for step in level]
        self.executor.execute(ctx)
        return ctx
