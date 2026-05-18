from __future__ import annotations

import dataclasses
from typing import ClassVar

from psycopg.types.json import Jsonb

from pipeline.core.base_stage import BaseStage
from pipeline.core.db import connect
from pipeline.questions.models.pipeline_models import Problem
from pipeline.questions.stages.generate_concept_questions import GenerateConceptQuestions
from pipeline.questions.stages.generate_hypotheticals import GenerateHypotheticals
from pipeline.questions.stages.generate_questions import GenerateQuestions
from pipeline.questions.state import QuestionState


_SCHEMA = """
CREATE TABLE IF NOT EXISTS repos (
    id          TEXT PRIMARY KEY,
    name        TEXT,
    url         TEXT,
    indexed_at  TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE repos ALTER COLUMN indexed_at DROP NOT NULL;

CREATE TABLE IF NOT EXISTS clusters (
    id        TEXT NOT NULL,
    repo_id   TEXT NOT NULL REFERENCES repos(id) ON DELETE CASCADE,
    level     INT  NOT NULL,
    title     TEXT,
    summary   TEXT,
    PRIMARY KEY (repo_id, id)
);

ALTER TABLE clusters ADD COLUMN IF NOT EXISTS title TEXT;

CREATE TABLE IF NOT EXISTS concept_groups (
    id            TEXT NOT NULL,
    repo_id       TEXT NOT NULL REFERENCES repos(id) ON DELETE CASCADE,
    label         TEXT NOT NULL,
    member_tags   JSONB NOT NULL,
    file_paths    JSONB NOT NULL,
    PRIMARY KEY (repo_id, id)
);

CREATE TABLE IF NOT EXISTS problems (
    problem_id        UUID PRIMARY KEY,
    repo_id           TEXT NOT NULL REFERENCES repos(id) ON DELETE CASCADE,
    concept_id        TEXT,
    concept_group_id  TEXT,
    kind              TEXT NOT NULL,
    prompt            TEXT NOT NULL,
    explanation       TEXT NOT NULL,
    citations         JSONB NOT NULL,
    payload           JSONB NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (repo_id, concept_id) REFERENCES clusters(repo_id, id) ON DELETE CASCADE,
    FOREIGN KEY (repo_id, concept_group_id) REFERENCES concept_groups(repo_id, id) ON DELETE CASCADE
);

ALTER TABLE problems ALTER COLUMN concept_id DROP NOT NULL;
ALTER TABLE problems ADD COLUMN IF NOT EXISTS concept_group_id TEXT;

CREATE INDEX IF NOT EXISTS problems_repo_concept_idx        ON problems (repo_id, concept_id);
CREATE INDEX IF NOT EXISTS problems_repo_concept_group_idx  ON problems (repo_id, concept_group_id);
CREATE INDEX IF NOT EXISTS problems_repo_kind_idx           ON problems (repo_id, kind);
"""

_COMMON_FIELDS = frozenset(
    {"problem_id", "concept_id", "concept_group_id", "prompt", "explanation", "citations"}
)


def _payload_for(problem: Problem) -> dict:
    return {
        k: v
        for k, v in dataclasses.asdict(problem).items()
        if k not in _COMMON_FIELDS
    }


class PersistQuestions(BaseStage):
    depends_on: ClassVar[tuple[type["BaseStage"], ...]] = (
        GenerateQuestions,
        GenerateHypotheticals,
        GenerateConceptQuestions,
    )

    def run(self, ctx: QuestionState) -> None:
        repo = ctx.db.get_repo()
        if repo is None:
            raise RuntimeError("repo.db has no repo row; cannot persist questions")

        all_clusters = ctx.db.all_clusters()
        all_concept_groups = ctx.db.all_concept_groups()

        with connect() as conn, conn.cursor() as cur:
            cur.execute(_SCHEMA)

            cur.execute("DELETE FROM repos WHERE id = %s", (repo.id,))

            cur.execute(
                "INSERT INTO repos (id, name, url) VALUES (%s, %s, %s)",
                (repo.id, repo.name, repo.repo_url),
            )

            cur.executemany(
                "INSERT INTO clusters (id, repo_id, level, title, summary) "
                "VALUES (%s, %s, %s, %s, %s)",
                [
                    (c.id, repo.id, c.level, c.title, c.summary)
                    for c in all_clusters
                ],
            )

            cur.executemany(
                "INSERT INTO concept_groups (id, repo_id, label, member_tags, file_paths) "
                "VALUES (%s, %s, %s, %s, %s)",
                [
                    (
                        g.id,
                        repo.id,
                        g.label,
                        Jsonb(g.member_tags),
                        Jsonb(g.file_paths),
                    )
                    for g in all_concept_groups
                ],
            )

            cur.executemany(
                "INSERT INTO problems "
                "(problem_id, repo_id, concept_id, concept_group_id, kind, prompt, "
                "explanation, citations, payload) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                [
                    (
                        p.problem_id,
                        repo.id,
                        p.concept_id,
                        p.concept_group_id,
                        type(p).__name__,
                        p.prompt,
                        p.explanation,
                        Jsonb(p.citations),
                        Jsonb(_payload_for(p)),
                    )
                    for p in ctx.problems
                ],
            )

        print(
            f"[persist_questions] wrote {len(ctx.problems)} problems "
            f"({len(all_clusters)} clusters, {len(all_concept_groups)} concept groups) "
            f"for repo {repo.id}"
        )
