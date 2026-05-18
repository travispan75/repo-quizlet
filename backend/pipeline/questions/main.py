import sys
from pathlib import Path

from pipeline.questions import QuestionPipeline


_REPOS_ROOT = Path(__file__).resolve().parent / "repos"


def main(argv: list[str]) -> None:
    if len(argv) != 2:
        print("Usage: python -m pipeline.questions.main <repo-id>")
        sys.exit(1)

    repo_id = argv[1]
    db_path = _REPOS_ROOT / repo_id / "repo.db"
    if not db_path.exists():
        print(f"No repo.db found at {db_path}")
        sys.exit(1)

    state = QuestionPipeline().run(db_path=db_path)
    print(f"Generated {len(state.problems)} problems for {repo_id}")


if __name__ == "__main__":
    main(sys.argv)
