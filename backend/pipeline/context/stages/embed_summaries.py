import dataclasses
from typing import ClassVar

from sentence_transformers import SentenceTransformer

from pipeline.context import State
from pipeline.core.base_stage import BaseStage
from pipeline.context.stages.summarize_clusters import SummarizeClusters
from pipeline.context.stages.summarize_repo import SummarizeRepo


_EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
_BATCH_SIZE = 512


class EmbedSummaries(BaseStage):
    depends_on: ClassVar[tuple[type["BaseStage"], ...]] = (
        SummarizeClusters,
        SummarizeRepo,
    )

    def __init__(self, model_name: str = _EMBEDDING_MODEL) -> None:
        self._model = SentenceTransformer(model_name)

    def run(self, ctx: State) -> None:
        self._embed_clusters(ctx)
        self._embed_repo(ctx)

    def _embed_clusters(self, ctx: State) -> None:
        located = [
            (layer_idx, cid)
            for layer_idx, layer in enumerate(ctx.graph_clusters)
            for cid, cluster in layer.items()
            if cluster.summary is not None
        ]
        if not located:
            return
        summaries = [ctx.graph_clusters[layer_idx][cid].summary for layer_idx, cid in located]
        embeddings = self._encode(summaries)
        for (layer_idx, cid), embedding in zip(located, embeddings):
            ctx.graph_clusters[layer_idx][cid] = dataclasses.replace(
                ctx.graph_clusters[layer_idx][cid],
                embedding=embedding.tolist(),
            )

    def _embed_repo(self, ctx: State) -> None:
        if not ctx.repo_summary:
            return
        embeddings = self._encode([ctx.repo_summary])
        ctx.repo_embedding = embeddings[0].tolist()

    def _encode(self, texts: list[str]):
        return self._model.encode(
            texts,
            batch_size=_BATCH_SIZE,
            show_progress_bar=True,
            convert_to_numpy=True,
        )
