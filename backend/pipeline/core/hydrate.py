"""Restore cloned source from Supabase when missing on local disk."""

from __future__ import annotations

import os
from pathlib import Path

from pipeline.core.storage import SupabaseStorage, extract_tarball


def hydrate_repo_source(job_id: str, repo_path: Path, tmp_root: Path) -> bool:
    """Download and extract source tarball if ``repo_path`` is absent. Returns True if present after."""
    if repo_path.exists():
        return True
    bucket = os.environ.get("SUPABASE_SOURCES_BUCKET")
    if not bucket:
        return False
    try:
        storage = SupabaseStorage(bucket)
    except Exception:
        return False
    tmp = tmp_root / job_id
    tmp.mkdir(parents=True, exist_ok=True)
    tar_local = tmp / "source.tar.gz"
    try:
        if not storage.download_file(f"{job_id}/source.tar.gz", tar_local):
            return False
        repo_path.parent.mkdir(parents=True, exist_ok=True)
        extract_tarball(tar_local, repo_path.parent)
        return repo_path.exists()
    except Exception:
        return False
    finally:
        tar_local.unlink(missing_ok=True)
