from __future__ import annotations

import hashlib
import inspect
from pathlib import Path

import cloudpickle
import pytest

from pipeline.context import State, ContextPipeline
from pipeline.context.stages import cluster_graphs
from pipeline.core.base_stage import BaseStage
from pipeline.core.dag_scheduler import DagScheduler


CACHE_DIR = Path(__file__).parent / ".ctx_cache"


def _collect_deps_excluding(target: type[BaseStage]) -> list[type[BaseStage]]:
    """Collect every transitive dependency of `target`, but NOT `target` itself."""
    seen: set[type[BaseStage]] = set()
    order: list[type[BaseStage]] = []

    def visit(stage: type[BaseStage]) -> None:
        if stage in seen:
            return
        seen.add(stage)
        for dep in stage.depends_on:
            visit(dep)
        order.append(stage)

    for dep in target.depends_on:
        visit(dep)
    return order


def _digest_for(stages: list[type[BaseStage]]) -> str:
    src = "".join(inspect.getsource(stage) for stage in stages)
    return hashlib.sha1(src.encode("utf-8")).hexdigest()[:12]


def _gc_old_caches(prefix: str, keep: str) -> None:
    if not CACHE_DIR.exists():
        return
    for path in CACHE_DIR.glob(f"{prefix}_*.pkl"):
        if path.name != keep:
            try:
                path.unlink()
            except OSError:
                pass


@pytest.fixture(autouse=True)
def _seed_louvain(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cluster_graphs, "_RANDOM_STATE", 0)


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--ctx-repo",
        help="Path to the repo to index when populating fixtures.",
    )
    parser.addoption(
        "--ctx-repo-name",
        help="Repo name passed into the State.",
    )


@pytest.fixture(scope="session")
def ctx_factory(request: pytest.FixtureRequest):
    repo_path = request.config.getoption("--ctx-repo")
    repo_name = request.config.getoption("--ctx-repo-name")
    if not repo_path:
        pytest.fail("--ctx-repo is required (path to the repo to index)")
    if not repo_name:
        pytest.fail("--ctx-repo-name is required (name passed into the State)")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def build(stage_under_test: type[BaseStage] | None = None) -> State:
        """Return a `ctx` ready for `stage_under_test` to run on.

        - `stage_under_test=None` runs the full pipeline (all `Pipeline.steps`).
        - Otherwise runs every transitive dependency of `stage_under_test`,
          but NOT `stage_under_test` itself. The test then runs the stage
          fresh, so iterating on that stage doesn't bust the upstream cache.
        """
        if stage_under_test is None:
            stages = list(ContextPipeline.steps)
            prefix = "full"
        else:
            stages = _collect_deps_excluding(stage_under_test)
            prefix = f"before_{stage_under_test.__name__}"
        digest = _digest_for(stages)
        filename = f"{prefix}_{digest}.pkl"
        cache_path = CACHE_DIR / filename

        if not cache_path.exists():
            ctx = State(repo_path=repo_path, repo_name=repo_name)
            scheduled = DagScheduler().schedule(stages)
            for level in scheduled:
                for Stage in level:
                    Stage().run(ctx)
            cache_path.write_bytes(cloudpickle.dumps(ctx))
            _gc_old_caches(prefix, filename)

        return cloudpickle.loads(cache_path.read_bytes())

    return build
