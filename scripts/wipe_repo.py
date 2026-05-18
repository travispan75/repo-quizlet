"""Wipe all state for a single repo, addressed by its repo id.

Usage:
    python scripts/wipe_repo.py <repo_id>

Wipes:
    - Filesystem: cloned source, repo.db, context/questions LLM caches, tmp.
    - Redis: progress key, any queued / in-flight jobs for this id.
    - Supabase Storage: source tarball + repo.db + cache tarballs.
    - Postgres: the `repos` row (cascades to clusters / concept_groups / problems).

Each step is best-effort and logs its outcome; a failure in one step does not
stop the rest. The Postgres row is dropped last so a partial wipe is re-runnable.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_BACKEND_ROOT = _REPO_ROOT / "backend"
_PIPELINE_ROOT = _BACKEND_ROOT / "pipeline"

sys.path.insert(0, str(_BACKEND_ROOT))

from pipeline.core.db import connect
from pipeline.core.storage import SupabaseStorage
from pipeline.worker.redis_client import RedisClient


_FS_PATHS_FOR = lambda repo_id: [
    _BACKEND_ROOT / "data" / "repos" / repo_id,
    _PIPELINE_ROOT / "questions" / "repos" / repo_id,
    _PIPELINE_ROOT / "context" / ".cache" / repo_id,
    _PIPELINE_ROOT / "questions" / ".cache" / repo_id,
    _PIPELINE_ROOT / ".cache_tmp" / repo_id,
]

_QUEUE = "repo_jobs"
_PROCESSING = "repo_jobs:processing"

_ARTIFACT_KEYS = [
    "repo.db",
    "context-cache.tar.gz",
    "questions-cache.tar.gz",
]


def _force_remove_readonly(func, path, _exc_info):
    # Windows git packs (and others) mark files read-only, which trips rmtree.
    # Chmod to writable and retry the same operation that failed.
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        raise


def _wipe_filesystem(repo_id: str) -> None:
    removed = 0
    for path in _FS_PATHS_FOR(repo_id):
        if not path.exists():
            continue
        try:
            if path.is_dir():
                shutil.rmtree(path, onerror=_force_remove_readonly)
            else:
                path.unlink()
            removed += 1
            print(f"[fs]       removed {path}")
        except Exception as e:
            print(f"[fs]       FAILED {path}: {e}")
    print(f"[fs]       done ({removed} paths)")


def _purge_list(client: RedisClient, key: str, repo_id: str) -> int:
    items = client.client.lrange(key, 0, -1) or []
    purged = 0
    for raw in items:
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError):
            continue
        if payload.get("job_id") != repo_id:
            continue
        client.client.lrem(key, 0, raw)
        purged += 1
    return purged


def _wipe_redis(repo_id: str) -> None:
    try:
        client = RedisClient()
    except Exception as e:
        print(f"[redis]    FAILED to connect: {e}")
        return

    try:
        client.client.delete(f"progress:{repo_id}")
        print(f"[redis]    deleted progress:{repo_id}")
    except Exception as e:
        print(f"[redis]    FAILED progress key: {e}")

    for key in (_QUEUE, _PROCESSING):
        try:
            purged = _purge_list(client, key, repo_id)
            print(f"[redis]    purged {purged} job(s) from {key}")
        except Exception as e:
            print(f"[redis]    FAILED scrubbing {key}: {e}")


def _wipe_storage(repo_id: str) -> None:
    sources_bucket = os.environ.get("SUPABASE_SOURCES_BUCKET")
    artifacts_bucket = os.environ.get("SUPABASE_ARTIFACTS_BUCKET")

    if sources_bucket:
        try:
            count = SupabaseStorage(sources_bucket).delete_prefix(repo_id)
            print(f"[storage]  deleted {count} object(s) from {sources_bucket}/{repo_id}")
        except Exception as e:
            print(f"[storage]  FAILED {sources_bucket}: {e}")
    else:
        print("[storage]  SUPABASE_SOURCES_BUCKET not set; skipping")

    if artifacts_bucket:
        try:
            count = SupabaseStorage(artifacts_bucket).delete_prefix(repo_id)
            print(f"[storage]  deleted {count} object(s) from {artifacts_bucket}/{repo_id}")
        except Exception as e:
            print(f"[storage]  FAILED {artifacts_bucket}: {e}")
    else:
        print("[storage]  SUPABASE_ARTIFACTS_BUCKET not set; skipping")


def _wipe_postgres(repo_id: str) -> None:
    try:
        with connect() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM repos WHERE id = %s", (repo_id,))
            print(f"[postgres] deleted {cur.rowcount} repo row (cascade fired)")
    except Exception as e:
        print(f"[postgres] FAILED: {e}")


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: python scripts/wipe_repo.py <repo_id>", file=sys.stderr)
        sys.exit(2)

    repo_id = sys.argv[1].strip().lower()
    if not repo_id:
        print("error: empty repo_id", file=sys.stderr)
        sys.exit(2)

    print(f"Wiping repo {repo_id}")
    _wipe_filesystem(repo_id)
    _wipe_redis(repo_id)
    _wipe_storage(repo_id)
    _wipe_postgres(repo_id)
    print("Done.")


if __name__ == "__main__":
    main()
