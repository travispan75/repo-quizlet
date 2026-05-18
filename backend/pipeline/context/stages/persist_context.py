import json
import sqlite3
from pathlib import Path
from typing import ClassVar

import numpy as np

from pipeline.context import State
from pipeline.core.base_stage import BaseStage
from pipeline.context.stages.build_cluster_subgraphs import BuildClusterSubgraphs
from pipeline.context.stages.build_concept_groups import BuildConceptGroups
from pipeline.context.stages.summarize_files import SummarizeFiles
from pipeline.context.stages.summarize_repo import SummarizeRepo
from pipeline.context.stages.title_clusters import TitleClusters


_PERSIST_ROOT = Path(__file__).resolve().parents[2] / "questions" / "repos"


_SCHEMA = """
CREATE TABLE repo (
    id TEXT PRIMARY KEY,
    name TEXT,
    summary TEXT,
    embedding BLOB,
    file_tree TEXT,
    repo_url TEXT,
    readme TEXT
);

CREATE TABLE clusters (
    id TEXT PRIMARY KEY,
    title TEXT,
    summary TEXT,
    embedding BLOB,
    subgraph TEXT
);

CREATE TABLE files (
    id TEXT PRIMARY KEY,
    path TEXT NOT NULL,
    language TEXT,
    contents TEXT,
    summary TEXT,
    concepts TEXT,
    cluster_id TEXT,
    dependencies TEXT,
    FOREIGN KEY (cluster_id) REFERENCES clusters(id)
);

CREATE TABLE concept_groups (
    id TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    member_tags TEXT NOT NULL,
    file_paths TEXT NOT NULL
);

CREATE TABLE symbols (
    id TEXT PRIMARY KEY,
    display_name TEXT,
    kind TEXT,
    language TEXT,
    file_id TEXT,
    enclosing_symbol_id TEXT,
    signature TEXT,
    documentation TEXT,
    calls TEXT,
    called_by TEXT,
    FOREIGN KEY (file_id) REFERENCES files(id)
);

CREATE TABLE occurrences (
    id TEXT PRIMARY KEY,
    symbol_id TEXT NOT NULL,
    file_id TEXT NOT NULL,
    start_line INTEGER,
    start_char INTEGER,
    end_line INTEGER,
    end_char INTEGER,
    role_flags INTEGER NOT NULL,
    is_definition INTEGER,
    is_reference INTEGER,
    is_import INTEGER,
    enclosing_symbol_id TEXT,
    FOREIGN KEY (symbol_id) REFERENCES symbols(id),
    FOREIGN KEY (file_id) REFERENCES files(id)
);

CREATE INDEX idx_files_cluster ON files(cluster_id);
CREATE INDEX idx_symbols_file ON symbols(file_id);
CREATE INDEX idx_occurrences_symbol ON occurrences(symbol_id);
CREATE INDEX idx_occurrences_file ON occurrences(file_id);
CREATE INDEX idx_occurrences_enclosing ON occurrences(enclosing_symbol_id);
"""


def _embedding_to_blob(emb: list[float] | None) -> bytes | None:
    if emb is None:
        return None
    return np.asarray(emb, dtype=np.float32).tobytes()


def _read_file_contents(repo_root: Path, relative_path: str) -> str | None:
    full_path = repo_root / relative_path
    try:
        return full_path.read_text(encoding="utf-8", errors="replace")
    except (OSError, ValueError):
        return None


class PersistContext(BaseStage):
    depends_on: ClassVar[tuple[type["BaseStage"], ...]] = (
        BuildClusterSubgraphs,
        BuildConceptGroups,
        SummarizeFiles,
        SummarizeRepo,
        TitleClusters,
    )

    def run(self, ctx: State) -> None:
        repo_id = ctx.job_id or Path(ctx.repo_path).name
        db_dir = _PERSIST_ROOT / repo_id
        db_dir.mkdir(parents=True, exist_ok=True)
        db_path = db_dir / "repo.db"

        if db_path.exists():
            db_path.unlink()

        conn = sqlite3.connect(db_path)
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.executescript(_SCHEMA)

            self._write_repo(conn, ctx, repo_id)
            self._write_clusters(conn, ctx)
            self._write_files(conn, ctx)
            self._write_symbols(conn, ctx)
            self._write_occurrences(conn, ctx)
            self._write_concept_groups(conn, ctx)

            conn.commit()
        finally:
            conn.close()

    def _write_repo(self, conn: sqlite3.Connection, ctx: State, repo_id: str) -> None:
        conn.execute(
            "INSERT INTO repo (id, name, summary, embedding, file_tree, repo_url, readme) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                repo_id,
                ctx.repo_name,
                ctx.repo_summary,
                _embedding_to_blob(ctx.repo_embedding),
                ctx.file_tree,
                ctx.repo_url,
                ctx.readme,
            ),
        )

    def _write_clusters(self, conn: sqlite3.Connection, ctx: State) -> None:
        rows = [
            (
                cluster.cluster_id,
                cluster.title,
                cluster.summary,
                _embedding_to_blob(cluster.embedding),
                json.dumps(cluster.subgraph) if cluster.subgraph is not None else None,
            )
            for layer in ctx.graph_clusters
            for cluster in layer.values()
        ]
        conn.executemany(
            "INSERT INTO clusters (id, title, summary, embedding, subgraph) "
            "VALUES (?, ?, ?, ?, ?)",
            rows,
        )

    def _write_files(self, conn: sqlite3.Connection, ctx: State) -> None:
        file_to_cluster: dict[str, str] = {}
        all_clusters = [
            cluster for layer in ctx.graph_clusters for cluster in layer.values()
        ]
        clusters_by_size = sorted(all_clusters, key=lambda c: len(c.files))
        for cluster in clusters_by_size:
            for file_path in cluster.files:
                if file_path not in file_to_cluster:
                    file_to_cluster[file_path] = cluster.cluster_id

        repo_root = Path(ctx.repo_path)
        rows = []
        for file in ctx.file_table.values():
            contents = _read_file_contents(repo_root, file.file_path)
            cluster_id = file_to_cluster.get(file.file_path)
            dependencies = {
                target: int(weight)
                for target, weight in ctx.dependency_graph.get(file.file_path, {}).items()
                if target in ctx.file_table
            }
            rows.append(
                (
                    file.file_path,
                    file.file_path,
                    file.language,
                    contents,
                    file.summary,
                    json.dumps(list(file.concepts)),
                    cluster_id,
                    json.dumps(dependencies),
                )
            )
        conn.executemany(
            "INSERT INTO files (id, path, language, contents, summary, concepts, cluster_id, dependencies) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )

    def _write_symbols(self, conn: sqlite3.Connection, ctx: State) -> None:
        rows = []
        for symbol in ctx.symbol_table.values():
            file_paths = ctx.symbol_to_file_map.get(symbol.symbol_id, set())
            file_id = next(iter(file_paths), None)
            if file_id is not None and file_id not in ctx.file_table:
                file_id = None
            rows.append(
                (
                    symbol.symbol_id,
                    symbol.display_name,
                    symbol.kind,
                    symbol.language,
                    file_id,
                    symbol.enclosing_symbol_id,
                    symbol.signature,
                    symbol.documentation,
                    json.dumps(sorted(symbol.calls)),
                    json.dumps(sorted(symbol.called_by)),
                )
            )
        conn.executemany(
            "INSERT INTO symbols "
            "(id, display_name, kind, language, file_id, enclosing_symbol_id, signature, documentation, "
            "calls, called_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )

    def _write_concept_groups(self, conn: sqlite3.Connection, ctx: State) -> None:
        rows = [
            (
                g.group_id,
                g.label,
                json.dumps(list(g.member_tags)),
                json.dumps(list(g.file_paths)),
            )
            for g in ctx.concept_groups
        ]
        conn.executemany(
            "INSERT INTO concept_groups (id, label, member_tags, file_paths) "
            "VALUES (?, ?, ?, ?)",
            rows,
        )

    def _write_occurrences(self, conn: sqlite3.Connection, ctx: State) -> None:
        rows = []
        for occ in ctx.occurrence_table.values():
            if occ.symbol_id not in ctx.symbol_table:
                continue
            if occ.file_path not in ctx.file_table:
                continue
            enclosing = (
                occ.enclosing_symbol_id
                if occ.enclosing_symbol_id in ctx.symbol_table
                else None
            )
            rows.append(
                (
                    occ.occurrence_id,
                    occ.symbol_id,
                    occ.file_path,
                    occ.start_line,
                    occ.start_character,
                    occ.end_line,
                    occ.end_character,
                    occ.role_flags,
                    int(occ.is_definition),
                    int(occ.is_reference),
                    int(occ.is_import),
                    enclosing,
                )
            )
        conn.executemany(
            "INSERT INTO occurrences "
            "(id, symbol_id, file_id, start_line, start_char, end_line, end_char, "
            "role_flags, is_definition, is_reference, is_import, enclosing_symbol_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
