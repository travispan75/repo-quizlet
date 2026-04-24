from pipeline.scip.scip_indexer import ScipIndexer


class ScipTypescriptIndexer(ScipIndexer):
    docker_image = "scip-typescript"
    docker_file = "pipeline/scip/scip_artifacts/docker-images/typescript/Dockerfile"

    def build_cmd(self, repo_path: str, repo_name: str, output_path: str) -> list[str]:
        return ["scip-typescript", "index", "--project-root", repo_path, "--output", output_path]
