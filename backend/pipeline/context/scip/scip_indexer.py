import os
import shutil
import subprocess
from pathlib import Path


_BUGGY = 'new RegExp(o.sep,"g")'
_FIXED = r'new RegExp(o.sep==="\\"?"\\\\":o.sep,"g")'

_DEFAULT_BUNDLE = (
    Path(__file__).resolve().parents[3]
    / "node_modules"
    / "@sourcegraph"
    / "scip-python"
    / "dist"
    / "scip-python.js"
)


def _resolve_node() -> str:
    override = os.environ.get("NODE_BIN")
    if override:
        return override
    found = shutil.which("node")
    if not found:
        raise RuntimeError(
            "node executable not found on PATH. Install Node.js 18+ "
            "(https://nodejs.org) or set NODE_BIN."
        )
    return found


def _resolve_bundle() -> Path:
    override = os.environ.get("SCIP_PYTHON_BUNDLE")
    if override:
        return Path(override)
    return _DEFAULT_BUNDLE


def _ensure_windows_patch(bundle: Path) -> None:
    """
    scip-python ships a bug that crashes Node on Windows:
        new RegExp(path.sep, 'g')   // path.sep === '\' -> invalid regex
    The fix is harmless on Linux (the buggy substring isn't present after
    the first patch, and the patched form is a valid regex on both OSes).
    Run idempotently on every startup so npm install doesn't undo it.
    """
    try:
        src = bundle.read_text(encoding="utf-8")
    except OSError as e:
        raise RuntimeError(
            f"scip-python bundle not found at {bundle}. "
            "Run `npm install` in backend/."
        ) from e
    if _BUGGY in src:
        bundle.write_text(src.replace(_BUGGY, _FIXED, 1), encoding="utf-8")


class ScipIndexer:
    def run(self, repo_path: str, repo_name: str, output_path: str) -> None:
        node = _resolve_node()
        bundle = _resolve_bundle()
        _ensure_windows_patch(bundle)

        cmd = [
            node,
            str(bundle),
            "index",
            "--cwd", repo_path,
            "--project-name", repo_name,
            "--output", output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"scip-python failed (exit {result.returncode})\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            )
