"""One-shot inspector for the LLM-summary caches.

Run:
    python pipeline/State/tests/inspect_cache.py

Writes a human-readable dump of cached chunk/cluster/repo summaries
to pipeline/State/out2.log so you can eyeball quality without running pytest.
"""

import json
from pathlib import Path

_PIPELINE_ROOT = Path(__file__).resolve().parents[1]
_CACHE_DIR = _PIPELINE_ROOT / ".cache"
_OUTPUT = _PIPELINE_ROOT / "out2.log"
_CHUNK_SAMPLE = 50


def _load(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    chunk_cache = _load(_CACHE_DIR / "chunk_summaries.json")
    cluster_cache = _load(_CACHE_DIR / "cluster_summaries.json")
    repo_cache = _load(_CACHE_DIR / "repo_summaries.json")

    lines: list[str] = []

    lines.append("=" * 70)
    lines.append(
        f"CHUNK SUMMARIES  (showing {min(_CHUNK_SAMPLE, len(chunk_cache))} of {len(chunk_cache)})"
    )
    lines.append("=" * 70)
    for i, (h, summary) in enumerate(chunk_cache.items()):
        if i >= _CHUNK_SAMPLE:
            break
        lines.append(f"[{h[:12]}]  {summary}")

    lines.append("")
    lines.append("=" * 70)
    lines.append(f"CLUSTER SUMMARIES  ({len(cluster_cache)} total)")
    lines.append("=" * 70)
    if not cluster_cache:
        lines.append("(none cached yet)")
    for h, summary in cluster_cache.items():
        lines.append(f"[{h[:12]}]")
        lines.append(summary)
        lines.append("")

    lines.append("")
    lines.append("=" * 70)
    lines.append(f"REPO SUMMARIES  ({len(repo_cache)} total)")
    lines.append("=" * 70)
    if not repo_cache:
        lines.append("(none cached yet)")
    for h, summary in repo_cache.items():
        lines.append(f"[{h[:12]}]")
        lines.append(summary)
        lines.append("")

    _OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {_OUTPUT} ({len(lines)} lines)")


if __name__ == "__main__":
    main()
