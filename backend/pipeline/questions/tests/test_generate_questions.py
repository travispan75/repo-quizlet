from dataclasses import fields
from pathlib import Path

from pipeline.questions import QuestionPipeline


_REPOS_ROOT = Path(__file__).resolve().parents[1] / "repos"


def test_generate_questions_dump(repo_id: str) -> None:
    db_path = _REPOS_ROOT / repo_id / "repo.db"
    assert db_path.exists(), f"No repo.db at {db_path}"

    state = QuestionPipeline().run(db_path=db_path)

    print(f"\n=== Generated {len(state.problems)} problems for {repo_id} ===")

    by_concept: dict[str, list] = {}
    for problem in state.problems:
        by_concept.setdefault(problem.concept_id, []).append(problem)

    for concept_id in sorted(by_concept):
        problems = by_concept[concept_id]
        print(f"\n----- {concept_id} ({len(problems)} problems) -----")
        for problem in problems:
            print(f"\n[{type(problem).__name__}] {problem.prompt}")
            for field in fields(problem):
                if field.name in ("problem_id", "concept_id", "prompt"):
                    continue
                print(f"  {field.name}: {getattr(problem, field.name)}")
