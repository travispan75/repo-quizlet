"""FastAPI server for the stateless Next.js frontend.

The worker (``pipeline.worker.main``) runs in a separate process and talks to the
same state (Postgres, Redis, Supabase Storage, ``data/repos/<id>/``) directly.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from pipeline.core.db import connect
from pipeline.core.hydrate import hydrate_repo_source
from pipeline.worker.redis_client import RedisClient


_BACKEND_ROOT = Path(__file__).resolve().parent
_SOURCE_ROOT = _BACKEND_ROOT / "data" / "repos"
_TMP_ROOT = _BACKEND_ROOT / "pipeline" / ".cache_tmp"
_ENV_PATH = _BACKEND_ROOT / ".env"
_MAX_FILE_BYTES = 2_000_000

_TREE_IGNORE = frozenset({
    ".git", "node_modules", ".next", "__pycache__",
    ".venv", "venv", "dist", "build",
})

_ALLOWED_HOSTS = {"github.com", "gitlab.com", "bitbucket.org"}


load_dotenv(_ENV_PATH)

app = FastAPI(title="Repo Quiz API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
_redis = RedisClient()


class SubmitRepoBody(BaseModel):
    url: str


def _normalize_url(raw: str) -> str | None:
    try:
        u = urlparse(raw)
    except Exception:
        return None
    if not u.netloc:
        return None
    host = u.netloc.lower().split("@")[-1].split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    if host not in _ALLOWED_HOSTS:
        return None
    path = u.path.rstrip("/")
    if path.endswith(".git"):
        path = path[:-4]
    return urlunparse(("https", host, path, "", "", ""))


def _repo_name(url: str) -> str:
    parts = [p for p in urlparse(url).path.split("/") if p]
    return parts[-1] if parts else "unknown-repo"


def _ensure_schema() -> None:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS repos (
                id          TEXT PRIMARY KEY,
                name        TEXT,
                url         TEXT,
                indexed_at  TIMESTAMPTZ DEFAULT now()
            )
            """
        )
        cur.execute("ALTER TABLE repos ALTER COLUMN indexed_at DROP NOT NULL")
        cur.execute("DELETE FROM repos WHERE url IS NULL OR url = ''")
        conn.commit()


def _safe_join(root: Path, rel: str) -> Path | None:
    try:
        candidate = (root / rel).resolve()
    except Exception:
        return None
    root_resolved = root.resolve()
    if candidate != root_resolved and root_resolved not in candidate.parents:
        return None
    return candidate


def _repo_root(repo_id: str) -> Path:
    root = _SOURCE_ROOT / repo_id
    if not root.exists():
        hydrate_repo_source(repo_id, root, _TMP_ROOT)
    return root


_EXT_TO_LANG = {
    "ts": "typescript", "tsx": "tsx", "js": "javascript", "jsx": "jsx",
    "mjs": "javascript", "cjs": "javascript", "py": "python", "rb": "ruby",
    "go": "go", "rs": "rust", "java": "java", "kt": "kotlin",
    "c": "c", "h": "c", "cpp": "cpp", "hpp": "cpp", "cs": "csharp",
    "php": "php", "swift": "swift", "json": "json", "yaml": "yaml",
    "yml": "yaml", "toml": "toml", "md": "markdown", "mdx": "mdx",
    "sh": "bash", "bash": "bash", "zsh": "bash", "ps1": "powershell",
    "html": "html", "css": "css", "scss": "scss", "sql": "sql",
    "xml": "xml", "proto": "proto", "rst": "markdown",
}


def _lang_for(filename: str) -> str:
    lower = filename.lower()
    if lower == "dockerfile":
        return "docker"
    ext = lower.rsplit(".", 1)[-1] if "." in lower else ""
    return _EXT_TO_LANG.get(ext, "text")


def _looks_binary(buf: bytes) -> bool:
    return b"\x00" in buf[:8000]


def _build_tree(root_abs: Path, rel_dir: str = "") -> list[dict[str, Any]]:
    abs_dir = root_abs / rel_dir if rel_dir else root_abs
    try:
        entries = list(abs_dir.iterdir())
    except OSError:
        return []
    nodes: list[dict[str, Any]] = []
    for e in entries:
        if e.name in _TREE_IGNORE:
            continue
        rel = f"{rel_dir}/{e.name}".lstrip("/") if rel_dir else e.name
        if e.is_dir():
            nodes.append({
                "name": e.name,
                "path": rel,
                "type": "dir",
                "children": _build_tree(root_abs, rel),
            })
        elif e.is_file():
            nodes.append({"name": e.name, "path": rel, "type": "file"})
    nodes.sort(key=lambda n: (0 if n["type"] == "dir" else 1, n["name"].lower()))
    return nodes


@app.get("/healthz")
def healthz() -> dict[str, bool]:
    return {"ok": True}


@app.post("/api/repos")
def submit_repo(body: SubmitRepoBody) -> dict[str, str]:
    url = body.url.strip()
    if not url:
        raise HTTPException(400, "Please enter a URL")

    normalized = _normalize_url(url)
    if not normalized:
        raise HTTPException(
            400,
            "Only GitHub, GitLab, and Bitbucket links are supported",
        )

    repo_id = hashlib.sha1(normalized.encode("utf-8")).hexdigest()
    repo_name = _repo_name(normalized)

    _ensure_schema()

    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO repos (id, name, url, indexed_at)
            VALUES (%s, %s, %s, NULL)
            ON CONFLICT (id) DO NOTHING
            RETURNING true AS inserted
            """,
            (repo_id, repo_name, normalized),
        )
        just_claimed = cur.fetchone() is not None
        if not just_claimed:
            cur.execute(
                "SELECT indexed_at IS NULL FROM repos WHERE id = %s",
                (repo_id,),
            )
            row = cur.fetchone()
            if row and row[0]:
                conn.commit()
                return {"id": repo_id}
            cur.execute(
                "UPDATE repos SET name = %s, url = %s, indexed_at = NULL WHERE id = %s",
                (repo_name, normalized, repo_id),
            )
        conn.commit()

    try:
        _redis.enqueue(
            "repo_jobs",
            json.dumps({
                "job_id": repo_id,
                "repo_name": repo_name,
                "repo_url": normalized,
            }),
        )
    except Exception:
        if just_claimed:
            with connect() as conn, conn.cursor() as cur:
                cur.execute("DELETE FROM repos WHERE id = %s", (repo_id,))
                conn.commit()
        raise HTTPException(503, "Job queue unavailable, try again.")

    return {"id": repo_id}


@app.get("/api/repos")
def list_repos() -> list[dict[str, Any]]:
    _ensure_schema()
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, name, url, indexed_at FROM repos
            ORDER BY indexed_at IS NULL DESC, indexed_at DESC
            """
        )
        rows = cur.fetchall()
    return [
        {
            "id": r[0],
            "name": r[1] or r[0][:8],
            "url": r[2] or "",
            "indexed_at": r[3].isoformat() if r[3] else None,
        }
        for r in rows
    ]


@app.get("/api/repos/{repo_id}")
def get_repo(repo_id: str) -> dict[str, Any]:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, name, url, indexed_at FROM repos WHERE id = %s",
            (repo_id,),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(404, "not found")
    return {
        "id": row[0],
        "name": row[1] or row[0][:8],
        "url": row[2] or "",
        "indexed_at": row[3].isoformat() if row[3] else None,
    }


@app.get("/api/repos/{repo_id}/progress")
def get_progress(repo_id: str) -> dict[str, Any]:
    raw = _redis.client.get(f"progress:{repo_id}")
    if not raw:
        return {"status": "idle"}
    try:
        return json.loads(raw)
    except Exception:
        return {"status": "idle"}


@app.get("/api/repos/{repo_id}/tree")
def get_tree(repo_id: str) -> dict[str, Any]:
    root = _repo_root(repo_id)
    if not root.exists() or not root.is_dir():
        raise HTTPException(404, "repo not on disk")
    return {"tree": _build_tree(root)}


@app.get("/api/repos/{repo_id}/file")
def get_file(repo_id: str, path: str = Query("")) -> dict[str, Any]:
    rel = path.strip()
    if not rel:
        raise HTTPException(400, "path required")
    root = _repo_root(repo_id)
    abs_path = _safe_join(root, rel)
    if not abs_path or not abs_path.exists() or not abs_path.is_file():
        raise HTTPException(404, "file not found")
    size = abs_path.stat().st_size
    if size > _MAX_FILE_BYTES:
        raise HTTPException(413, detail={
            "error": "file too large",
            "size": size,
            "max": _MAX_FILE_BYTES,
        })
    buf = abs_path.read_bytes()
    if _looks_binary(buf):
        return {"path": rel, "binary": True, "size": size}
    return {
        "path": rel,
        "binary": False,
        "size": size,
        "language": _lang_for(abs_path.name),
        "contents": buf.decode("utf-8", errors="replace"),
    }


@app.get("/api/repos/{repo_id}/problems")
def get_problems(repo_id: str) -> dict[str, Any]:
    try:
        with connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT problem_id, concept_id, concept_group_id, kind,
                       prompt, explanation, citations, payload
                FROM problems
                WHERE repo_id = %s
                ORDER BY concept_id NULLS LAST,
                         concept_group_id NULLS LAST,
                         problem_id
                """,
                (repo_id,),
            )
            rows = cur.fetchall()
    except Exception as e:
        if "does not exist" in str(e).lower():
            return {"problems": []}
        raise
    return {
        "problems": [
            {
                "problem_id": r[0],
                "concept_id": r[1],
                "concept_group_id": r[2],
                "kind": r[3],
                "prompt": r[4],
                "explanation": r[5],
                "citations": r[6] or [],
                "payload": r[7] or {},
            }
            for r in rows
        ],
    }


@app.get("/api/repos/{repo_id}/topics")
def get_topics(repo_id: str) -> dict[str, Any]:
    cluster_titles: dict[str, str] = {}
    concept_labels: dict[str, str] = {}
    try:
        with connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT id, title FROM clusters WHERE repo_id = %s",
                (repo_id,),
            )
            for cid, title in cur.fetchall():
                if title:
                    cluster_titles[cid] = title
    except Exception as e:
        if "does not exist" not in str(e).lower():
            raise
    try:
        with connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT id, label FROM concept_groups WHERE repo_id = %s",
                (repo_id,),
            )
            for cid, label in cur.fetchall():
                if label:
                    concept_labels[cid] = label
    except Exception as e:
        if "does not exist" not in str(e).lower():
            raise
    return {
        "cluster_titles": cluster_titles,
        "concept_group_labels": concept_labels,
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "5000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
