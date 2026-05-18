from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(slots=True, frozen=True)
class Repo:
    id: str
    name: str | None
    summary: str | None
    file_tree: str | None
    readme: str | None
    repo_url: str | None


@dataclass(slots=True, frozen=True)
class Cluster:
    id: str
    level: int
    title: str | None
    summary: str | None
    subgraph: dict[str, dict[str, int]] | None


@dataclass(slots=True, frozen=True)
class File:
    id: str
    path: str
    language: str | None
    contents: str | None
    summary: str | None
    concepts: list[str]
    cluster_id: str | None
    dependencies: dict[str, int]


@dataclass(slots=True, frozen=True)
class ConceptGroup:
    id: str
    label: str
    member_tags: list[str]
    file_paths: list[str]


@dataclass(slots=True, frozen=True)
class Symbol:
    id: str
    display_name: str | None
    kind: str | None
    language: str | None
    file_id: str | None
    enclosing_symbol_id: str | None
    signature: str | None
    documentation: str | None
    calls: list[str]
    called_by: list[str]


def _level_from_id(cluster_id: str) -> int:
    return int(cluster_id.split("_", 1)[0][1:])


def _row_to_repo(row: sqlite3.Row) -> Repo:
    return Repo(
        id=row["id"],
        name=row["name"],
        summary=row["summary"],
        file_tree=row["file_tree"],
        readme=row["readme"],
        repo_url=row["repo_url"],
    )


def _row_to_cluster(row: sqlite3.Row) -> Cluster:
    return Cluster(
        id=row["id"],
        level=_level_from_id(row["id"]),
        title=row["title"],
        summary=row["summary"],
        subgraph=json.loads(row["subgraph"]) if row["subgraph"] else None,
    )


def _row_to_file(row: sqlite3.Row) -> File:
    return File(
        id=row["id"],
        path=row["path"],
        language=row["language"],
        contents=row["contents"],
        summary=row["summary"],
        concepts=json.loads(row["concepts"]) if _has_col(row, "concepts") and row["concepts"] else [],
        cluster_id=row["cluster_id"],
        dependencies=json.loads(row["dependencies"]) if row["dependencies"] else {},
    )


def _row_to_concept_group(row: sqlite3.Row) -> ConceptGroup:
    return ConceptGroup(
        id=row["id"],
        label=row["label"],
        member_tags=json.loads(row["member_tags"]) if row["member_tags"] else [],
        file_paths=json.loads(row["file_paths"]) if row["file_paths"] else [],
    )


def _has_col(row: sqlite3.Row, name: str) -> bool:
    try:
        return name in row.keys()
    except Exception:
        return False


def _row_to_symbol(row: sqlite3.Row) -> Symbol:
    return Symbol(
        id=row["id"],
        display_name=row["display_name"],
        kind=row["kind"],
        language=row["language"],
        file_id=row["file_id"],
        enclosing_symbol_id=row["enclosing_symbol_id"],
        signature=row["signature"],
        documentation=row["documentation"],
        calls=json.loads(row["calls"]) if row["calls"] else [],
        called_by=json.loads(row["called_by"]) if row["called_by"] else [],
    )


class RepoDB:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self._local = threading.local()

    @property
    def _conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return conn

    def close(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None

    def __enter__(self) -> "RepoDB":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ---- repo ----
    def get_repo(self) -> Repo | None:
        row = self._conn.execute("SELECT * FROM repo LIMIT 1").fetchone()
        return _row_to_repo(row) if row else None

    # ---- clusters ----
    def get_cluster(self, cluster_id: str) -> Cluster | None:
        row = self._conn.execute(
            "SELECT * FROM clusters WHERE id = ?", (cluster_id,)
        ).fetchone()
        return _row_to_cluster(row) if row else None

    def all_clusters(self) -> list[Cluster]:
        return [_row_to_cluster(r) for r in self._conn.execute("SELECT * FROM clusters")]

    def clusters_at_level(self, level: int) -> list[Cluster]:
        prefix = f"L{level}_"
        return [
            _row_to_cluster(r)
            for r in self._conn.execute(
                "SELECT * FROM clusters WHERE id LIKE ?", (f"{prefix}%",)
            )
        ]

    # ---- files ----
    def get_file(self, file_id: str) -> File | None:
        row = self._conn.execute(
            "SELECT * FROM files WHERE id = ?", (file_id,)
        ).fetchone()
        return _row_to_file(row) if row else None

    def files_in_cluster(self, cluster_id: str) -> list[File]:
        return [
            _row_to_file(r)
            for r in self._conn.execute(
                "SELECT * FROM files WHERE cluster_id = ?", (cluster_id,)
            )
        ]

    def all_files(self) -> list[File]:
        return [_row_to_file(r) for r in self._conn.execute("SELECT * FROM files")]

    # ---- concept groups ----
    def all_concept_groups(self) -> list[ConceptGroup]:
        try:
            rows = self._conn.execute("SELECT * FROM concept_groups")
        except sqlite3.OperationalError:
            return []
        return [_row_to_concept_group(r) for r in rows]

    def files_by_paths(self, paths: Iterable[str]) -> list[File]:
        ids = list(paths)
        if not ids:
            return []
        placeholders = ",".join("?" * len(ids))
        return [
            _row_to_file(r)
            for r in self._conn.execute(
                f"SELECT * FROM files WHERE path IN ({placeholders})", ids
            )
        ]

    # ---- symbols ----
    def get_symbol(self, symbol_id: str) -> Symbol | None:
        row = self._conn.execute(
            "SELECT * FROM symbols WHERE id = ?", (symbol_id,)
        ).fetchone()
        return _row_to_symbol(row) if row else None

    def get_symbols(self, symbol_ids: Iterable[str]) -> list[Symbol]:
        ids = list(symbol_ids)
        if not ids:
            return []
        placeholders = ",".join("?" * len(ids))
        return [
            _row_to_symbol(r)
            for r in self._conn.execute(
                f"SELECT * FROM symbols WHERE id IN ({placeholders})", ids
            )
        ]

    def symbols_in_file(self, file_id: str) -> list[Symbol]:
        return [
            _row_to_symbol(r)
            for r in self._conn.execute(
                "SELECT * FROM symbols WHERE file_id = ?", (file_id,)
            )
        ]

    def symbols_in_cluster(self, cluster_id: str) -> list[Symbol]:
        return [
            _row_to_symbol(r)
            for r in self._conn.execute(
                "SELECT s.* FROM symbols s "
                "JOIN files f ON s.file_id = f.id "
                "WHERE f.cluster_id = ?",
                (cluster_id,),
            )
        ]
