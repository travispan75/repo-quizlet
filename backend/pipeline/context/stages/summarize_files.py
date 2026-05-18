import dataclasses
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import ClassVar

from tqdm import tqdm

from pipeline.context import State
from pipeline.core.llm import OpenAIClient
from pipeline.core.base_stage import BaseStage
from pipeline.context.stages.build_scip_base_tables import BuildScipBaseTables


_MAX_WORKERS = 16
_MAX_FILE_TOKENS = 8000
_CACHE_DIR = Path(__file__).resolve().parents[1] / ".cache"
_CACHE_NAME = "file_summaries.json"

_PROMPT = """Summarize the source file below in 2-4 sentences, then identify the concrete patterns or themes present in it.

`summary`:
- Describe concretely what the file does and its role in the codebase.
- Do not start with "this file", "this module", or "this code". Lead with action-oriented language (e.g., "Implements...", "Defines...", "Provides...").
- Flowing prose only - no bullet points, no markdown, no headings.

`concepts`:
- 2-5 short lowercase phrases naming specific patterns, idioms, or themes in this file.
- Examples of good concepts: "factory pattern", "lazy initialization", "context manager", "request lifecycle", "monkey patching", "dispatch table", "fluent builder", "error recovery", "request decorator".
- Be specific. PREFER design patterns (factory pattern, decorator, observer pattern), language idioms (context manager, descriptor protocol, async iterator), architectural roles (event loop, dispatch table, registry, dependency injection), or domain themes (request lifecycle, cache invalidation, retry policy).
- REJECTED concepts: "python", "javascript", "function", "code", "helper", "utility", "module", "class definition" - these are not specific enough.
- Use lowercase. Phrases like "factory pattern" or "request lifecycle" are fine; do not force snake_case or CamelCase.

PATH: {path}
LANGUAGE: {language}

CODE:
```
{code}
```"""


_RESPONSE_SCHEMA = {
    "name": "file_summary",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["summary", "concepts"],
        "properties": {
            "summary": {"type": "string"},
            "concepts": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 2,
                "maxItems": 5,
            },
        },
    },
}


class SummarizeFiles(BaseStage):
    depends_on: ClassVar[tuple[type["BaseStage"], ...]] = (BuildScipBaseTables,)

    def run(self, ctx: State) -> None:
        if not ctx.file_table:
            return

        repo_root = Path(ctx.repo_path)
        contents_by_file: dict[str, str] = {}
        for file_path in ctx.file_table:
            content = _read_file(repo_root, file_path)
            if content is not None:
                contents_by_file[file_path] = content

        if not contents_by_file:
            return

        client = OpenAIClient()
        cache = _load_cache(ctx.cache_key)

        hashes = {fp: _hash(contents_by_file[fp]) for fp in contents_by_file}
        used_hashes = set(hashes.values())
        pending = [
            fp for fp, h in hashes.items()
            if not _is_valid_entry(cache.get(h))
        ]

        if pending:
            with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as ex:
                futures = {
                    ex.submit(
                        _summarize_file,
                        client,
                        fp,
                        ctx.file_table[fp].language,
                        contents_by_file[fp],
                    ): fp
                    for fp in pending
                }
                total = len(futures)
                for i, fut in enumerate(
                    tqdm(
                        as_completed(futures),
                        total=total,
                        desc="summarize files",
                    ),
                    start=1,
                ):
                    fp = futures[fut]
                    cache[hashes[fp]] = fut.result()
                    ctx.progress.heartbeat(i, total)

        cache = {h: v for h, v in cache.items() if h in used_hashes and _is_valid_entry(v)}
        _save_cache(cache, ctx.cache_key)

        for fp, h in hashes.items():
            entry = cache.get(h)
            if not _is_valid_entry(entry):
                continue
            ctx.file_table[fp] = dataclasses.replace(
                ctx.file_table[fp],
                summary=entry["summary"],
                concepts=tuple(entry["concepts"]),
            )


def _summarize_file(
    client: OpenAIClient,
    path: str,
    language: str,
    code: str,
) -> dict:
    truncated = _truncate(code, _MAX_FILE_TOKENS)
    prompt = _PROMPT.format(path=path, language=language, code=truncated)
    try:
        result = client.generate_json(prompt, schema=_RESPONSE_SCHEMA)
    except Exception as e:
        print(f"[summarize_files] LLM call failed for {path}: {e}")
        return {"summary": "", "concepts": []}
    summary = str(result.get("summary", "")).strip()
    raw_concepts = result.get("concepts", []) or []
    concepts = [str(c).strip().lower() for c in raw_concepts if str(c).strip()]
    return {"summary": summary, "concepts": concepts}


def _is_valid_entry(entry) -> bool:
    return (
        isinstance(entry, dict)
        and isinstance(entry.get("summary"), str)
        and isinstance(entry.get("concepts"), list)
    )


def _read_file(repo_root: Path, relative_path: str) -> str | None:
    try:
        return (repo_root / relative_path).read_text(encoding="utf-8", errors="replace")
    except (OSError, ValueError):
        return None


def _truncate(text: str, max_tokens: int) -> str:
    if _approx_tokens(text) <= max_tokens:
        return text
    return text[: max_tokens * 4]


def _approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _cache_path(cache_key: str) -> Path:
    return _CACHE_DIR / cache_key / _CACHE_NAME


def _load_cache(cache_key: str) -> dict[str, dict]:
    path = _cache_path(cache_key)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
    return {}


def _save_cache(cache: dict[str, dict], cache_key: str) -> None:
    path = _cache_path(cache_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, indent=2), encoding="utf-8")
