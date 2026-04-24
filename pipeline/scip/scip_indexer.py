import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar


class ScipIndexer(ABC):
    docker_image: ClassVar[str]
    docker_file: ClassVar[str]

    @abstractmethod
    def build_cmd(self, repo_path: str, repo_name: str, output_path: str) -> list[str]:
        pass

    def _ensure_image(self) -> subprocess.CompletedProcess[str]:
        inspect_result = subprocess.run(
            args=["docker", "image", "inspect", self.__class__.docker_image],
            capture_output=True,
            text=True,
        )
        if inspect_result.returncode == 0:
            return inspect_result

        docker_file = Path(self.__class__.docker_file)
        build_result = subprocess.run(
            args=[
                "docker",
                "build",
                "--file",
                docker_file.as_posix(),
                "--tag",
                self.__class__.docker_image,
                docker_file.parent.as_posix(),
            ],
            capture_output=True,
            text=True,
        )
        if build_result.returncode != 0:
            raise RuntimeError(
                f"Failed to build Docker image {self.__class__.docker_image}\n"
                f"stdout:\n{build_result.stdout}\n"
                f"stderr:\n{build_result.stderr}"
            )
        return build_result

    def run(self, repo_path: str, repo_name: str, output_path: str) -> subprocess.CompletedProcess[str]:
        self._ensure_image()

        result = self._run_inner_cmd(
            repo_path=repo_path,
            repo_name=repo_name,
            output_path=output_path,
            inner_cmd=self.build_cmd(
                repo_path="/workspace/repo",
                repo_name=repo_name,
                output_path=f"/workspace/out/{Path(output_path).name}",
            ),
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"SCIP indexing failed for image {self.__class__.docker_image}\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            )
        return result

    def _run_inner_cmd(
        self,
        *,
        repo_path: str,
        repo_name: str,
        output_path: str,
        inner_cmd: list[str],
    ) -> subprocess.CompletedProcess[str]:
        repo_source_mount_path = "/workspace/repo-src"
        output_mount_path = "/workspace/out"
        output_dir = Path(output_path).parent.resolve()

        docker_cmd = [
            "docker",
            "run",
            "--rm",
            "--volume",
            f"{Path(repo_path).resolve()}:{repo_source_mount_path}:ro",
            "--volume",
            f"{output_dir}:{output_mount_path}",
            self.__class__.docker_image,
            *inner_cmd,
        ]

        return subprocess.run(args=docker_cmd, capture_output=True, text=True)
