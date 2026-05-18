import sqlite3
from pathlib import Path

from pipeline.context.stages import persist_context
from pipeline.context.stages.persist_context import PersistContext


_EXPECTED_TABLES = {"repo", "files", "symbols", "occurrences", "clusters"}


def test_persist_context_creates_db(ctx_factory, tmp_path, monkeypatch):
    monkeypatch.setattr(persist_context, "_PERSIST_ROOT", tmp_path)

    ctx = ctx_factory(PersistContext)
    PersistContext().run(ctx)

    repo_id = ctx.job_id or Path(ctx.repo_path).name
    db_path = tmp_path / repo_id / "repo.db"
    assert db_path.exists()

    conn = sqlite3.connect(db_path)
    try:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert tables == _EXPECTED_TABLES

        assert conn.execute("SELECT COUNT(*) FROM repo").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM files").fetchone()[0] > 0
        assert conn.execute("SELECT COUNT(*) FROM symbols").fetchone()[0] > 0
        assert conn.execute("SELECT COUNT(*) FROM clusters").fetchone()[0] > 0

        clusters_with_summary = conn.execute(
            "SELECT COUNT(*) FROM clusters WHERE summary IS NOT NULL"
        ).fetchone()[0]
        assert clusters_with_summary > 0

        clusters_with_subgraph = conn.execute(
            "SELECT COUNT(*) FROM clusters WHERE subgraph IS NOT NULL"
        ).fetchone()[0]
        assert clusters_with_subgraph > 0

        files_with_summary = conn.execute(
            "SELECT COUNT(*) FROM files WHERE summary IS NOT NULL"
        ).fetchone()[0]
        assert files_with_summary > 0

        repo_summary = conn.execute("SELECT summary FROM repo").fetchone()[0]
        assert repo_summary is not None and repo_summary.strip()

        symbols_with_calls = conn.execute(
            "SELECT COUNT(*) FROM symbols WHERE calls != '[]'"
        ).fetchone()[0]
        assert symbols_with_calls > 0

        symbols_with_called_by = conn.execute(
            "SELECT COUNT(*) FROM symbols WHERE called_by != '[]'"
        ).fetchone()[0]
        assert symbols_with_called_by > 0

        files_with_deps = conn.execute(
            "SELECT COUNT(*) FROM files WHERE dependencies != '{}'"
        ).fetchone()[0]
        assert files_with_deps > 0

        occurrences_with_role_flags = conn.execute(
            "SELECT COUNT(*) FROM occurrences WHERE role_flags > 0"
        ).fetchone()[0]
        assert occurrences_with_role_flags > 0

        occurrences_with_enclosing = conn.execute(
            "SELECT COUNT(*) FROM occurrences WHERE enclosing_symbol_id IS NOT NULL"
        ).fetchone()[0]
        assert occurrences_with_enclosing > 0
    finally:
        conn.close()
