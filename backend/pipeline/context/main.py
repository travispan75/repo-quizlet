"""Run the context pipeline from the CLI.

Usage:
    python -m pipeline.context.main <git-repo-url>

Clones (or pulls) the repo into ``backend/data/repos/<sha1(url)>/`` and runs
the full context pipeline against it. Mostly useful for one-off testing — in
normal operation the worker invokes the pipeline.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from urllib.parse import urlparse

from pipeline.context import ContextPipeline


_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_SOURCE_ROOT = _BACKEND_ROOT / "data" / "repos"


def _id_for(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()


def _name_for(url: str) -> str:
    parts = [p for p in urlparse(url).path.split("/") if p]
    return parts[-1] if parts else "unknown-repo"


def main(argv: list[str]) -> None:
    if len(argv) != 2:
        print("Usage: python -m pipeline.context.main <git-repo-url>")
        sys.exit(1)

    url = argv[1]
    repo_id = _id_for(url)
    repo_name = _name_for(url)
    repo_path = _SOURCE_ROOT / repo_id

    ContextPipeline().run(
        repo_path=str(repo_path),
        job_id=repo_id,
        repo_name=repo_name,
        repo_url=url,
    )


if __name__ == "__main__":
    main(sys.argv)
