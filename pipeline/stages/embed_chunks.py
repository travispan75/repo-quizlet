import dataclasses
from typing import ClassVar

from sentence_transformers import SentenceTransformer

from pipeline.context import Context
from pipeline.stages.base_stage import BaseStage
from pipeline.stages.build_chunks import BuildChunks


_EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
_BATCH_SIZE = 512


class EmbedChunks(BaseStage):
    depends_on: ClassVar[tuple[type["BaseStage"], ...]] = (BuildChunks,)

    def __init__(self, model_name: str = _EMBEDDING_MODEL) -> None:
        self._model = SentenceTransformer(model_name)

    def run(self, ctx: Context) -> None:
        if not ctx.chunks:
            return

        codes = [chunk.code for chunk in ctx.chunks]
        embeddings = self._model.encode(
            codes,
            batch_size=_BATCH_SIZE,
            show_progress_bar=True,
            convert_to_numpy=True,
        )

        ctx.chunks = [
            dataclasses.replace(chunk, embedding=embedding.tolist())
            for chunk, embedding in zip(ctx.chunks, embeddings)
        ]
