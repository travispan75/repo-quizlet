import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--repo-id",
        default="a3f8c2d1-4b5e-6f7a-8c9d-0e1f2a3b4c5d",
        help="Directory name under pipeline/questions/repos/ that holds repo.db.",
    )


@pytest.fixture(scope="session")
def repo_id(request: pytest.FixtureRequest) -> str:
    return request.config.getoption("--repo-id")
