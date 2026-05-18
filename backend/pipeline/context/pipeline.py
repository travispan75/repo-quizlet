from pipeline.context.state import State
from pipeline.context.stages.build_call_graph import BuildCallGraph
from pipeline.context.stages.build_cluster_subgraphs import BuildClusterSubgraphs
from pipeline.context.stages.build_concept_groups import BuildConceptGroups
from pipeline.context.stages.build_dependency_graph import BuildDependencyGraph
from pipeline.context.stages.build_file_symbol_maps import BuildFileSymbolMaps
from pipeline.context.stages.build_file_tree import BuildFileTree
from pipeline.context.stages.build_scip_base_tables import BuildScipBaseTables
from pipeline.context.stages.build_symbol_occurrence_maps import BuildSymbolOccurrenceMaps
from pipeline.context.stages.clone_repo import CloneRepo
from pipeline.context.stages.cluster_graphs import ClusterGraphs
from pipeline.context.stages.index_repo import IndexRepo
from pipeline.context.stages.parse_repo import ParseRepo
from pipeline.context.stages.persist_context import PersistContext
from pipeline.context.stages.prepare_repo_venv import PrepareRepoVenv
from pipeline.context.stages.summarize_clusters import SummarizeClusters
from pipeline.context.stages.summarize_files import SummarizeFiles
from pipeline.context.stages.summarize_repo import SummarizeRepo
from pipeline.context.stages.title_clusters import TitleClusters
from pipeline.core import Pipeline


class ContextPipeline(Pipeline):
    steps = (
        CloneRepo,
        ParseRepo,
        BuildFileTree,
        PrepareRepoVenv,
        IndexRepo,
        BuildScipBaseTables,
        BuildSymbolOccurrenceMaps,
        BuildFileSymbolMaps,
        BuildCallGraph,
        BuildDependencyGraph,
        ClusterGraphs,
        BuildClusterSubgraphs,
        SummarizeFiles,
        BuildConceptGroups,
        SummarizeClusters,
        TitleClusters,
        SummarizeRepo,
        PersistContext,
    )

    def run(
        self,
        repo_path: str,
        job_id: str | None = None,
        repo_name: str | None = None,
        repo_url: str | None = None,
    ) -> State:
        ctx = State(
            repo_path=repo_path,
            job_id=job_id,
            repo_name=repo_name,
            repo_url=repo_url,
            progress=self.progress,
        )
        self.executor.levels = self.scheduler.schedule(list(self.steps))
        self.executor.execute(ctx)
        return ctx
