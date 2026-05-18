from __future__ import annotations

import subprocess
from pathlib import Path
from typing import ClassVar

from pipeline.context.state import State
from pipeline.core.base_stage import BaseStage


class CloneRepo(BaseStage):
    """Clone the upstream repo (or git pull if already present) onto local disk.

    Sets ``ctx.source_changed`` to True if this run brought in new commits, so
    downstream storage upload can be skipped when nothing changed.
    """

    depends_on: ClassVar[tuple[type["BaseStage"], ...]] = ()

    def run(self, ctx: State) -> None:
        if not ctx.repo_url:
            raise RuntimeError("repo_url is required to run CloneRepo")

        repo_path = Path(ctx.repo_path)

        if (repo_path / ".git").exists():
            before = _rev_parse(repo_path)
            _pull(repo_path)
            after = _rev_parse(repo_path)
            ctx.source_changed = before != after
        else:
            if repo_path.exists():
                _rmtree(repo_path)
            _clone(ctx.repo_url, repo_path)
            ctx.source_changed = True

        ctx.progress.mark_repo_updated(ctx.source_changed)


def _rev_parse(repo_path: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _clone(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["git", "clone", "--depth", "1", url, str(dest)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git clone {url} failed (exit {result.returncode}): {result.stderr.strip()}"
        )


def _pull(repo_path: Path) -> None:
    result = subprocess.run(
        ["git", "pull", "--ff-only"],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git pull in {repo_path} failed (exit {result.returncode}): {result.stderr.strip()}"
        )


def _rmtree(path: Path) -> None:
    import os
    import shutil
    import stat

    def force_remove_readonly(func, target, _info):
        try:
            os.chmod(target, stat.S_IWRITE)
            func(target)
        except Exception:
            raise

    shutil.rmtree(path, onerror=force_remove_readonly)
