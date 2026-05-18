from __future__ import annotations

import hashlib
from collections import Counter
from typing import ClassVar

import numpy as np
from sentence_transformers import SentenceTransformer

from pipeline.context import State
from pipeline.context.models import ConceptGroup
from pipeline.context.stages.cluster_graphs import ClusterGraphs
from pipeline.context.stages.summarize_files import SummarizeFiles
from pipeline.core.base_stage import BaseStage


_EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
_SIMILARITY_THRESHOLD = 0.75
_MIN_FILES = 3
_MIN_LOUVAIN_CLUSTERS = 2


class BuildConceptGroups(BaseStage):
    depends_on: ClassVar[tuple[type["BaseStage"], ...]] = (
        SummarizeFiles,
        ClusterGraphs,
    )

    def run(self, ctx: State) -> None:
        tag_to_files = _collect_tag_files(ctx)
        if len(tag_to_files) < 2:
            return

        file_to_louvain = _file_to_louvain_cluster(ctx)
        if not file_to_louvain:
            return

        tags = sorted(tag_to_files.keys())
        embeddings = _embed_tags(tags)
        clusters = _cluster_by_cosine(embeddings, _SIMILARITY_THRESHOLD)

        groups: list[ConceptGroup] = []
        for tag_indices in clusters:
            member_tags = [tags[i] for i in tag_indices]
            files: set[str] = set()
            for tag in member_tags:
                files.update(tag_to_files[tag])
            louvain_clusters = {
                file_to_louvain[f] for f in files if f in file_to_louvain
            }
            if len(files) < _MIN_FILES:
                continue
            if len(louvain_clusters) < _MIN_LOUVAIN_CLUSTERS:
                continue

            label = _pick_canonical_label(member_tags, tag_to_files)
            group_id = _make_group_id(member_tags)
            groups.append(
                ConceptGroup(
                    group_id=group_id,
                    label=label,
                    member_tags=tuple(sorted(member_tags)),
                    file_paths=tuple(sorted(files)),
                )
            )

        ctx.concept_groups = groups


def _collect_tag_files(ctx: State) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for fp, file in ctx.file_table.items():
        for tag in file.concepts:
            t = tag.strip().lower()
            if not t:
                continue
            out.setdefault(t, []).append(fp)
    return out


def _file_to_louvain_cluster(ctx: State) -> dict[str, str]:
    if not ctx.graph_clusters:
        return {}
    layer = ctx.graph_clusters[0]
    out: dict[str, str] = {}
    for cluster_id, cluster in layer.items():
        for fp in cluster.files:
            out.setdefault(fp, cluster_id)
    return out


def _embed_tags(tags: list[str]) -> np.ndarray:
    model = SentenceTransformer(_EMBEDDING_MODEL)
    vectors = model.encode(
        tags,
        batch_size=64,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    return vectors


def _cluster_by_cosine(vectors: np.ndarray, threshold: float) -> list[list[int]]:
    n = vectors.shape[0]
    if n == 0:
        return []
    sim = vectors @ vectors.T
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i in range(n):
        for j in range(i + 1, n):
            if sim[i, j] >= threshold:
                union(i, j)

    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return list(groups.values())


def _pick_canonical_label(member_tags: list[str], tag_to_files: dict[str, list[str]]) -> str:
    counts = Counter({t: len(tag_to_files[t]) for t in member_tags})
    raw = counts.most_common(1)[0][0]
    return _title_case_label(raw)


_ACRONYM_TOKENS = {
    "api", "cli", "url", "uri", "http", "https", "html", "css", "json", "yaml",
    "xml", "sql", "tcp", "udp", "ip", "ui", "ux", "io", "os", "id", "uuid",
    "jwt", "orm", "cors", "csrf", "dns", "ssl", "tls", "ssh", "ftp", "mvc",
    "rest", "rpc", "sdk", "ide", "asgi", "wsgi",
}


def _title_case_label(text: str) -> str:
    """Title-case a concept tag while preserving common acronyms.

    "factory pattern" -> "Factory Pattern"
    "test-driven development" -> "Test-Driven Development"
    "api routing" -> "API Routing"
    """
    def fix_token(tok: str) -> str:
        lower = tok.lower()
        if lower in _ACRONYM_TOKENS:
            return lower.upper()
        return tok[:1].upper() + tok[1:].lower() if tok else tok

    parts: list[str] = []
    for word in text.split(" "):
        sub = "-".join(fix_token(p) for p in word.split("-"))
        parts.append(sub)
    return " ".join(parts)


def _make_group_id(member_tags: list[str]) -> str:
    canonical = "\n".join(sorted(member_tags))
    digest = hashlib.sha1(canonical.encode("utf-8")).hexdigest()[:12]
    return f"concept_{digest}"
