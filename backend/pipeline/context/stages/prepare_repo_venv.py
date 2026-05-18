from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import ClassVar

from pipeline.context import State
from pipeline.context.stages.parse_repo import ParseRepo
from pipeline.core.base_stage import BaseStage


# Pyright (and therefore scip-python) auto-detects a venv named ".venv"
# at the repo root via its pyrightconfig logic. We also drop a tiny
# pyrightconfig.json next to it for fully explicit pickup.
_VENV_NAME = ".venv"
_PYRIGHT_CONFIG_NAME = "pyrightconfig.json"
_HASH_FILE = ".scip_deps_hash"
_INSTALL_TIMEOUT_S = 90
_PIP_CACHE = Path(__file__).resolve().parents[1] / ".cache" / "pip"

_DEP_FILES = ("pyproject.toml", "setup.py", "setup.cfg", "requirements.txt")


def _hash_dep_files(repo: Path) -> str:
    h = hashlib.sha256()
    for name in _DEP_FILES:
        p = repo / name
        if p.is_file():
            h.update(name.encode("utf-8"))
            h.update(b"\0")
            try:
                h.update(p.read_bytes())
            except OSError:
                continue
            h.update(b"\0")
    return h.hexdigest()[:16]


def _detect_install_command(repo: Path, pip: Path) -> list[str] | None:
    """
    Pick the right pip invocation for this repo. Best-effort heuristic:
    - pyproject.toml or setup.py present -> install the project itself,
      which pulls in its runtime deps (works for libraries like flask).
    - else requirements.txt -> install only the listed deps.
    - else None -> nothing to install.
    """
    if (repo / "pyproject.toml").is_file() or (repo / "setup.py").is_file():
        return [str(pip), "install", "--no-input", "--disable-pip-version-check", "."]
    if (repo / "requirements.txt").is_file():
        return [
            str(pip), "install", "--no-input", "--disable-pip-version-check",
            "-r", "requirements.txt",
        ]
    return None


def _write_pyright_config(repo: Path) -> None:
    cfg = {
        "venvPath": ".",
        "venv": _VENV_NAME,
        "useLibraryCodeForTypes": True,
    }
    (repo / _PYRIGHT_CONFIG_NAME).write_text(
        json.dumps(cfg, indent=2), encoding="utf-8"
    )


def _create_venv(repo: Path, venv_dir: Path) -> None:
    if venv_dir.exists():
        shutil.rmtree(venv_dir, ignore_errors=True)
    subprocess.run(
        [sys.executable, "-m", "venv", str(venv_dir)],
        check=True,
        capture_output=True,
    )


def _venv_pip(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "pip.exe"
    return venv_dir / "bin" / "pip"


class PrepareRepoVenv(BaseStage):
    depends_on: ClassVar[tuple[type["BaseStage"], ...]] = (ParseRepo,)

    def run(self, ctx: State) -> None:
        if "python" not in ctx.language_list:
            return

        repo = Path(ctx.repo_path)
        venv_dir = repo / _VENV_NAME
        hash_path = venv_dir / _HASH_FILE
        deps_hash = _hash_dep_files(repo)

        if not deps_hash:
            # No dep files at all - nothing to install, but still mark the
            # venv-less path so IndexRepo doesn't wait on anything.
            return

        if venv_dir.exists() and hash_path.is_file():
            try:
                if hash_path.read_text(encoding="utf-8").strip() == deps_hash:
                    _write_pyright_config(repo)
                    return
            except OSError:
                pass

        try:
            _create_venv(repo, venv_dir)
        except subprocess.CalledProcessError as e:
            print(
                f"[prepare_repo_venv] venv creation failed: {e.stderr.decode(errors='replace')}"
            )
            return

        install_cmd = _detect_install_command(repo, _venv_pip(venv_dir))
        if install_cmd is None:
            hash_path.write_text(deps_hash, encoding="utf-8")
            _write_pyright_config(repo)
            return

        _PIP_CACHE.mkdir(parents=True, exist_ok=True)
        env = {**os.environ, "PIP_CACHE_DIR": str(_PIP_CACHE)}
        try:
            subprocess.run(
                install_cmd,
                cwd=str(repo),
                env=env,
                check=True,
                capture_output=True,
                timeout=_INSTALL_TIMEOUT_S,
            )
            hash_path.write_text(deps_hash, encoding="utf-8")
        except subprocess.TimeoutExpired:
            print(
                f"[prepare_repo_venv] pip install timed out after "
                f"{_INSTALL_TIMEOUT_S}s; continuing without resolved deps"
            )
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode(errors="replace") if e.stderr else ""
            tail = "\n".join(stderr.splitlines()[-10:])
            print(
                f"[prepare_repo_venv] pip install failed (exit {e.returncode}); "
                f"continuing without resolved deps:\n{tail}"
            )

        _write_pyright_config(repo)
