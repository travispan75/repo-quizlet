import json
import os
import time
from pathlib import Path

from pipeline.context import ContextPipeline
from pipeline.core.db import connect
from pipeline.core.storage import SupabaseStorage, extract_tarball, make_tarball
from pipeline.questions import QuestionPipeline
from pipeline.worker.progress import RedisProgressReporter
from pipeline.worker.redis_client import RedisClient


_QUEUE = "repo_jobs"
_PROCESSING = "repo_jobs:processing"
_PIPELINE_ROOT = Path(__file__).resolve().parents[1]
_BACKEND_ROOT = _PIPELINE_ROOT.parent
_SOURCE_ROOT = _BACKEND_ROOT / "data" / "repos"
_REPOS_ROOT = _PIPELINE_ROOT / "questions" / "repos"
_CONTEXT_CACHE = _PIPELINE_ROOT / "context" / ".cache"
_QUESTIONS_CACHE = _PIPELINE_ROOT / "questions" / ".cache"
_TMP_ROOT = _PIPELINE_ROOT / ".cache_tmp"
_MAX_ATTEMPTS = 3
_SOURCE_EXCLUDES = frozenset({
    ".venv", "venv", "__pycache__", "node_modules", ".git",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", ".tox",
    "dist", "build", ".idea", ".vscode",
})


def _db_path_for(job_id: str) -> Path:
    return _REPOS_ROOT / job_id / "repo.db"


def _drop_repo_row(job_id: str) -> None:
    try:
        with connect() as conn, conn.cursor() as cur:
            cur.execute(
                "DELETE FROM repos WHERE id = %s AND indexed_at IS NULL",
                (job_id,),
            )
    except Exception as e:
        print(f"[worker] failed to drop in-flight repo row {job_id}: {e}")


def _sources_bucket() -> str | None:
    return os.environ.get("SUPABASE_SOURCES_BUCKET")


def _artifacts_bucket() -> str | None:
    return os.environ.get("SUPABASE_ARTIFACTS_BUCKET")


def _safe_exists(storage: SupabaseStorage, key: str) -> bool:
    try:
        return storage.exists(key)
    except Exception:
        return False


def _hydrate(job_id: str, repo_path: Path) -> None:
    sources_name = _sources_bucket()
    artifacts_name = _artifacts_bucket()
    if not sources_name or not artifacts_name:
        return
    try:
        sources = SupabaseStorage(sources_name)
        artifacts = SupabaseStorage(artifacts_name)
    except Exception as e:
        print(f"[worker] storage hydrate skipped ({e})")
        return

    tmp = _TMP_ROOT / job_id
    tmp.mkdir(parents=True, exist_ok=True)

    if not repo_path.exists():
        tar_local = tmp / "source.tar.gz"
        try:
            if sources.download_file(f"{job_id}/source.tar.gz", tar_local):
                print(f"[worker] restoring source for {job_id} from storage")
                repo_path.parent.mkdir(parents=True, exist_ok=True)
                extract_tarball(tar_local, repo_path.parent)
        except Exception as e:
            print(f"[worker] failed to restore source: {e}")
        finally:
            tar_local.unlink(missing_ok=True)

    db_path = _db_path_for(job_id)
    if not db_path.exists():
        try:
            if artifacts.download_file(f"{job_id}/repo.db", db_path):
                print(f"[worker] restored repo.db for {job_id} from storage")
        except Exception as e:
            print(f"[worker] failed to restore repo.db: {e}")

    ctx_cache_dir = _CONTEXT_CACHE / job_id
    if not ctx_cache_dir.exists():
        tar_local = tmp / "context-cache.tar.gz"
        try:
            if artifacts.download_file(f"{job_id}/context-cache.tar.gz", tar_local):
                print(f"[worker] restored context cache for {job_id}")
                extract_tarball(tar_local, _CONTEXT_CACHE)
        except Exception as e:
            print(f"[worker] failed to restore context cache: {e}")
        finally:
            tar_local.unlink(missing_ok=True)

    q_cache_dir = _QUESTIONS_CACHE / job_id
    if not q_cache_dir.exists():
        tar_local = tmp / "questions-cache.tar.gz"
        try:
            if artifacts.download_file(f"{job_id}/questions-cache.tar.gz", tar_local):
                print(f"[worker] restored questions cache for {job_id}")
                extract_tarball(tar_local, _QUESTIONS_CACHE)
        except Exception as e:
            print(f"[worker] failed to restore questions cache: {e}")
        finally:
            tar_local.unlink(missing_ok=True)


def _persist_after_context(job_id: str, repo_path: Path, source_changed: bool) -> None:
    sources_name = _sources_bucket()
    artifacts_name = _artifacts_bucket()
    if not sources_name or not artifacts_name:
        return
    try:
        sources = SupabaseStorage(sources_name)
        artifacts = SupabaseStorage(artifacts_name)
    except Exception as e:
        print(f"[worker] storage persist skipped ({e})")
        return

    tmp = _TMP_ROOT / job_id
    tmp.mkdir(parents=True, exist_ok=True)

    if repo_path.exists():
        src_key = f"{job_id}/source.tar.gz"
        should_upload = source_changed or not _safe_exists(sources, src_key)
        if not should_upload:
            print(f"[worker] source unchanged for {job_id}; skipping upload")
        else:
            src_tar = tmp / "source.tar.gz"
            try:
                make_tarball(repo_path, src_tar, exclude_names=_SOURCE_EXCLUDES)
                sources.upload_file(src_key, src_tar)
                print(f"[worker] uploaded source for {job_id}")
            except Exception as e:
                print(f"[worker] failed to upload source: {e}")
            finally:
                src_tar.unlink(missing_ok=True)

    db_path = _db_path_for(job_id)
    if db_path.exists():
        try:
            artifacts.upload_file(f"{job_id}/repo.db", db_path)
            print(f"[worker] uploaded repo.db for {job_id}")
        except Exception as e:
            print(f"[worker] failed to upload repo.db: {e}")

    ctx_cache_dir = _CONTEXT_CACHE / job_id
    if ctx_cache_dir.exists():
        ctx_tar = tmp / "context-cache.tar.gz"
        try:
            make_tarball(ctx_cache_dir, ctx_tar)
            artifacts.upload_file(f"{job_id}/context-cache.tar.gz", ctx_tar)
            print(f"[worker] uploaded context cache for {job_id}")
        except Exception as e:
            print(f"[worker] failed to upload context cache: {e}")
        finally:
            ctx_tar.unlink(missing_ok=True)


def _persist_after_questions(job_id: str) -> None:
    artifacts_name = _artifacts_bucket()
    if not artifacts_name:
        return
    try:
        artifacts = SupabaseStorage(artifacts_name)
    except Exception as e:
        print(f"[worker] storage persist skipped ({e})")
        return

    tmp = _TMP_ROOT / job_id
    tmp.mkdir(parents=True, exist_ok=True)

    q_cache_dir = _QUESTIONS_CACHE / job_id
    if q_cache_dir.exists():
        q_tar = tmp / "questions-cache.tar.gz"
        try:
            make_tarball(q_cache_dir, q_tar)
            artifacts.upload_file(f"{job_id}/questions-cache.tar.gz", q_tar)
            print(f"[worker] uploaded questions cache for {job_id}")
        except Exception as e:
            print(f"[worker] failed to upload questions cache: {e}")
        finally:
            q_tar.unlink(missing_ok=True)


def _retry_or_drop(
    client: RedisClient,
    raw: str,
    payload: dict,
    job_id: str,
    error: str,
) -> None:
    attempts = int(payload.get("attempts", 0)) + 1
    if attempts >= _MAX_ATTEMPTS:
        print(
            f"[worker] giving up on {job_id} after {attempts} attempts: {error}"
        )
        client.ack(_PROCESSING, raw)
        _drop_repo_row(job_id)
        time.sleep(1)
        return
    payload["attempts"] = attempts
    new_raw = json.dumps(payload)
    print(f"[worker] re-enqueueing {job_id} (attempt {attempts}/{_MAX_ATTEMPTS})")
    client.retry(_PROCESSING, _QUEUE, raw, new_raw)
    time.sleep(1)


def _process_one(client: RedisClient, raw: str, payload: dict) -> None:
    job_id = payload["job_id"]
    stage = payload.get("stage", "context")
    repo_path = _SOURCE_ROOT / job_id

    reporter = RedisProgressReporter(client, job_id)

    _hydrate(job_id, repo_path)

    source_changed = False
    if stage == "context":
        reporter.set_pipeline("context")
        try:
            pipeline = ContextPipeline(progress=reporter)
            ctx = pipeline.run(
                repo_path=str(repo_path),
                job_id=job_id,
                repo_name=payload["repo_name"],
                repo_url=payload["repo_url"],
            )
            source_changed = ctx.source_changed
        except Exception as e:
            err = str(e)
            print(f"[worker] context pipeline failed for {job_id}: {err}")
            reporter.failed(err)
            _retry_or_drop(client, raw, payload, job_id, err)
            return
        _persist_after_context(job_id, repo_path, source_changed=source_changed)
        stage = "questions"

    if stage == "questions":
        reporter.set_pipeline("questions")
        db_path = _db_path_for(job_id)
        if not db_path.exists():
            print(
                f"[worker] no repo.db at {db_path} for job {job_id}; "
                "re-running context pipeline"
            )
            payload["stage"] = "context"
            _retry_or_drop(client, raw, payload, job_id, "missing repo.db")
            return
        try:
            pipeline = QuestionPipeline(progress=reporter)
            pipeline.run(db_path=db_path)
        except Exception as e:
            err = str(e)
            print(f"[worker] questions pipeline failed for {job_id}: {err}")
            reporter.failed(err)
            payload["stage"] = "questions"
            _retry_or_drop(client, raw, payload, job_id, err)
            return
        _persist_after_questions(job_id)

    reporter.done()
    client.ack(_PROCESSING, raw)
    print(f"[worker] job {job_id} complete")


def main() -> None:
    client = RedisClient()
    rescued = client.recover_in_flight(_QUEUE, _PROCESSING)
    if rescued:
        print(f"[worker] rescued {rescued} in-flight job(s) from previous run")
    print("[worker] started; waiting for jobs")
    while True:
        try:
            raw = client.dequeue_reliable(_QUEUE, _PROCESSING)
            if raw is None:
                time.sleep(1)
                continue
            payload = json.loads(raw)
            _process_one(client, raw, payload)
        except KeyboardInterrupt:
            print("[worker] shutting down")
            return


if __name__ == "__main__":
    main()
