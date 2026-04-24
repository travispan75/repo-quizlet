from pipeline.scip.scip_indexer import ScipIndexer


class ScipPythonIndexer(ScipIndexer):
    docker_image = "scip-python"
    docker_file = "pipeline/scip/scip_artifacts/docker-images/python/Dockerfile"

    def build_cmd(self, repo_path: str, repo_name: str, output_path: str) -> list[str]:
        return ["scip-python", "index", "--cwd", repo_path, "--project-name", repo_name, "--output", output_path]
