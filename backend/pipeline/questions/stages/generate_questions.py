from __future__ import annotations

import hashlib
import json
import re
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import ClassVar

from tqdm import tqdm

from pipeline.core.base_stage import BaseStage
from pipeline.core.llm import OpenAIClient
from pipeline.questions.db import Cluster, RepoDB
from pipeline.questions.models.pipeline_models import Problem, ProblemFactory
from pipeline.questions.state import QuestionState


_MAX_WORKERS = 16
_CACHE_DIR = Path(__file__).resolve().parents[1] / ".cache"
_CACHE_NAME = "questions.json"

_TYPE_CAPS: dict[str, int] = {
    "MCQ":            5,
    "TF":             2,
    "MultipleSelect": 2,
    "Order":          2,
    "Pairing":        2,
    "Highlight":      2,
}

_LEVEL_DESCRIPTIONS = {
    0: "fine-grained (individual functions/methods/classes and the call edges between them)",
    1: "file-level (whole files and their dependency edges)",
}
_LEVEL_DEFAULT = "architectural (sub-clusters and the dependencies between them)"

_CITATION_RE = re.compile(r"^([^:]+):(\d+)(?:-(\d+))?$")

_PY_IMPORT_LINE_RE = re.compile(
    r"^\s*(?:from\s+[.\w]+\s+import\s+.+|import\s+\S.*?)\s*(?:#.*)?$"
)
_PY_REEXPORT_THRESHOLD = 0.8
_PY_REEXPORT_MIN_LINES = 3


def _str() -> dict:
    return {"type": "string"}


def _str_array(min_items: int, max_items: int) -> dict:
    return {
        "type": "array",
        "items": _str(),
        "minItems": min_items,
        "maxItems": max_items,
    }


def _str_pair_array(min_items: int, max_items: int) -> dict:
    return {
        "type": "array",
        "items": {
            "type": "array",
            "items": _str(),
            "minItems": 2,
            "maxItems": 2,
        },
        "minItems": min_items,
        "maxItems": max_items,
    }


def _obj(properties: dict[str, dict]) -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(properties.keys()),
        "properties": properties,
    }


def _common_fields(include_citations: bool) -> dict[str, dict]:
    fields: dict[str, dict] = {
        "prompt": _str(),
        "explanation": _str(),
    }
    if include_citations:
        fields["citations"] = _str_array(1, 5)
    return fields


def _make_item_schemas(include_citations: bool) -> dict[str, dict]:
    common = _common_fields(include_citations)
    return {
        "MCQ": _obj({
            **common,
            "correct": _str(),
            "distractors": _str_array(3, 3),
        }),
        "TF": _obj({
            **common,
            "is_true": {"type": "boolean"},
        }),
        "MultipleSelect": _obj({
            **common,
            "correct": _str_array(2, 4),
            "distractors": _str_array(2, 3),
        }),
        "Order": _obj({
            **common,
            "correct_order": _str_array(3, 6),
        }),
        "Pairing": _obj({
            **common,
            "pairs": _str_pair_array(3, 5),
        }),
        "Highlight": _obj({
            **common,
            "block": _str(),
            "correct": _str_array(1, 4),
        }),
    }


def _make_response_schema(include_citations: bool) -> dict:
    item_schemas = _make_item_schemas(include_citations)
    # Highlight needs source line numbers (block + correct), so it is only
    # available at L0 where full file contents with the gutter are visible.
    type_caps = (
        _TYPE_CAPS
        if include_citations
        else {k: v for k, v in _TYPE_CAPS.items() if k != "Highlight"}
    )
    return {
        "name": "cluster_questions",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": list(type_caps.keys()),
            "properties": {
                kind: {
                    "type": "array",
                    "items": item_schemas[kind],
                    "maxItems": cap,
                }
                for kind, cap in type_caps.items()
            },
        },
    }


_PER_KIND_SEMANTICS: dict[str, str] = {
    "MCQ":
        "`correct` + 3 `distractors` targeting real misconceptions about THIS code. "
        "Strong patterns: 'what happens if X?' (distractors are wrong outcomes), "
        "'how does X work?' (distractors are wrong algorithms), 'which is true about "
        "X's behavior?'.",
    "TF":
        "`prompt` is the FULL CLAIM (e.g., 'Calling `close_db` outside an app context "
        "raises an error.'). The claim must be unambiguously true or false; no trick "
        "wording.",
    "MultipleSelect":
        "2-4 `correct` + 2-3 `distractors`. Use only when MULTIPLE things are "
        "simultaneously true about ONE behavior. "
        "REJECTED: 'Which of these signals/routes/identifiers exist in the code?' - "
        "that is name-lookup, not comprehension.",
    "Order":
        "`correct_order` lists 3-6 steps IN CORRECT ORDER. Use when the source shows "
        "a real, non-arbitrary sequence. Each step must be a CONCRETE action visible "
        "in the source - NOT a generic abstraction like 'preprocess -> dispatch -> "
        "finalize' that would describe any web framework.",
    "Pairing":
        "3-5 `[left, right]` pairs. Right side describes HOW the left works "
        "(mechanism, internal steps, non-obvious consequence) - NEVER a restatement "
        "of the name. "
        "REJECTED: `get_db` -> 'connects to and returns the current database "
        "connection' (restates the name). "
        "ACCEPTED: `get_db` -> 'lazy-inits `g.db` on first call within a request, "
        "returns the cached connection on subsequent calls'.",
    "Highlight":
        "`block` and `correct` are STRINGS in the SAME `path/to/file.py:N-M` format "
        "as `citations` above - NEVER snippet text, code, or bare identifiers. "
        "`block` is ONE such string (8-30 lines, typically a function or branch) "
        "defining what the user sees. `correct` is 1-4 such strings in that same "
        "file, each with its line range fully inside `block`'s range, identifying "
        "lines that satisfy a sharp criterion. "
        "GOOD: `block` = \"src/flask/ctx.py:240-265\"; `correct` = "
        "[\"src/flask/ctx.py:248-251\", \"src/flask/ctx.py:259\"]. "
        "REJECTED `block`: \"def get_db()... return g.db\" (snippet text). "
        "REJECTED `correct`: [\"static_folder\", \"add_url_rule\"] (identifiers). "
        "Use when the answer is a SMALL SUBSET; if it would be most of `block`, "
        "use a different kind. "
        "ACCEPTED criterion: 'Which lines mutate `g`?' (subset of a request "
        "handler). REJECTED criterion: 'Which lines handle teardown?' (whole "
        "function is teardown).",
}


def _format_kinds_block(include_citations: bool) -> str:
    lines = []
    for kind, cap in _TYPE_CAPS.items():
        if kind == "Highlight" and not include_citations:
            continue
        lines.append(f"- {kind} (up to {cap}): {_PER_KIND_SEMANTICS[kind]}")
    return "\n".join(lines)


_CITATIONS_RULE = """
- CITATIONS: Every question MUST cite 1-3 source locations in `citations`. Each citation is the EXACT string `path/to/file.py:N` or `path/to/file.py:N-M` where:
    * `path/to/file.py` is one of the `=== ... ===` filenames shown above. Copy it verbatim.
    * `N` and `M` are line numbers read DIRECTLY from the `   N| ` gutter on the left of that file's source. Do NOT guess. Do NOT count. Do NOT include the gutter `| ` separator or any code in the citation string.
    * Cite lines containing the actual logic that justifies the answer (definitions, branches, returns, side effects). Do NOT cite import lines, blank lines, comment-only lines, docstring text, or files marked `Pure re-export module: not citable.`
  GOOD:  `"src/flask/signals.py:11"`
  GOOD:  `"examples/celery/src/task_app/__init__.py:7-26"`
  REJECTED: `"11| request_finished = _signals.signal(...)"`  (this is the gutter line itself, not a citation - it lacks the path and the `:`)
  REJECTED: `"src/flask/__init__.py:7"`  (re-export module; cite the file where the symbol is actually defined)
  REJECTED: `"src/flask/ctx.py:5"`  (line 5 is `from functools import update_wrapper`, an import - cite the line where the relevant logic lives)"""

_PROMPT_TEMPLATE = """You are creating quiz questions to help a developer learn and verify their understanding of a code repository. Below is a tightly-coupled group of code (a "cluster") at altitude {level_desc}.

ABSOLUTE RULES (violating any is a failure):
- GROUNDING: Do not invent functions, methods, classes, routes, commands, modules, files, or behaviors not literally present in the source below. Anything not visible above does not exist.{citations_rule}
- CANONICAL OUTPUT: Do NOT scramble, rotate, or shuffle - the frontend randomizes. Truth goes in its schema-designated field in canonical order.
- NO TRIVIA: Reject "what is the name of Y", "which of these strings/identifiers/routes exist", and any answer that is a literal restatement of an identifier (`send_static_file` -> "serves static files"). The question must depend on this code's specific BEHAVIOR, not on generic HTTP / Python / pytest / WSGI knowledge that would be true of any framework.
- BAR: A reader who SKIMMED the code should get it wrong; one who UNDERSTOOD it should get it right.

PREFER questions about: non-obvious behavior, control flow, lifecycle/teardown, error paths, invariants, hypothetical changes ("if X were removed, what breaks?"), edge cases, design trade-offs.

If the cluster's only material is name declarations, imports, or trivial stub code (e.g., a `signals.py` of `name = signal("name")` lines, or a hello-world demo), return EMPTY arrays for ALL kinds. Quality > quantity.

{structure_part}CONTENT:
{content_section}

KINDS:
{kinds_block}

OUTPUT: a JSON object with one field per kind (array of questions). Field shapes are schema-enforced.
"""


class GenerateQuestions(BaseStage):
    depends_on: ClassVar[tuple[type["BaseStage"], ...]] = ()

    def run(self, ctx: QuestionState) -> None:
        client = OpenAIClient()
        cache = _load_cache(ctx.cache_key)
        used_hashes: set[str] = set()
        all_files = ctx.db.all_files()
        all_paths = {f.path.replace("\\", "/") for f in all_files}
        file_line_counts: dict[str, int] = {
            f.path.replace("\\", "/"): len(f.contents.splitlines())
            for f in all_files
            if f.contents is not None
        }

        level = 0
        while True:
            clusters = ctx.db.clusters_at_level(level)
            if not clusters:
                break

            include_citations = level == 0
            schema = _make_response_schema(include_citations)

            jobs: list[tuple[Cluster, str, str]] = []
            for cluster in clusters:
                rendered = _render_cluster(ctx.db, cluster)
                if rendered is None:
                    continue
                prompt = _build_prompt(rendered, include_citations)
                job_hash = _hash_job(prompt, schema)
                used_hashes.add(job_hash)
                jobs.append((cluster, prompt, job_hash))

            pending = [j for j in jobs if j[2] not in cache]
            if pending:
                with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as ex:
                    futures = {
                        ex.submit(_call_llm, client, prompt, schema): (cluster, job_hash)
                        for cluster, prompt, job_hash in pending
                    }
                    total = len(futures)
                    for i, fut in enumerate(
                        tqdm(
                            as_completed(futures),
                            total=total,
                            desc=f"generate questions L{level}",
                        ),
                        start=1,
                    ):
                        _, job_hash = futures[fut]
                        cache[job_hash] = fut.result()
                        ctx.progress.heartbeat(i, total)
                _save_cache(cache, ctx.cache_key)

            for cluster, _prompt, job_hash in jobs:
                payload = cache[job_hash]
                if not isinstance(payload, dict):
                    continue
                for kind, items in payload.items():
                    if not isinstance(items, list):
                        continue
                    for item in items:
                        problem = _build_problem(
                            cluster.id,
                            kind,
                            item,
                            all_paths,
                            file_line_counts,
                            include_citations,
                        )
                        if problem is not None:
                            ctx.problems.append(problem)

            level += 1

        cache = {h: v for h, v in cache.items() if h in used_hashes}
        _save_cache(cache, ctx.cache_key)


def _render_cluster(db: RepoDB, cluster: Cluster) -> dict[str, str] | None:
    if cluster.subgraph is None:
        return None

    if cluster.level == 0:
        subgraph_text = _format_symbol_subgraph(db, cluster.id, cluster.subgraph)
        content_text = _format_files_full(db, cluster.id)
    elif cluster.level == 1:
        subgraph_text = _format_file_subgraph(cluster.subgraph)
        content_text = _format_file_summaries(db, cluster.subgraph)
    else:
        subgraph_text = _format_cluster_subgraph(cluster.subgraph)
        content_text = _format_cluster_summaries(db, cluster.subgraph)

    if not content_text.strip():
        return None

    return {
        "level_desc": _LEVEL_DESCRIPTIONS.get(cluster.level, _LEVEL_DEFAULT),
        "subgraph_section": subgraph_text,
        "content_section": content_text,
    }


def _build_prompt(rendered: dict[str, str], include_citations: bool) -> str:
    if rendered["subgraph_section"]:
        structure_part = (
            f"STRUCTURE (directed call/dependency edges among real symbols/files in this cluster):\n"
            f"{rendered['subgraph_section']}\n\n"
        )
    else:
        structure_part = ""
    return _PROMPT_TEMPLATE.format(
        level_desc=rendered["level_desc"],
        citations_rule=_CITATIONS_RULE if include_citations else "",
        structure_part=structure_part,
        content_section=rendered["content_section"],
        kinds_block=_format_kinds_block(include_citations),
    )


def _format_symbol_subgraph(
    db: RepoDB, cluster_id: str, subgraph: dict[str, dict[str, int]]
) -> str:
    symbols = db.symbols_in_cluster(cluster_id)
    by_id = {s.id: s for s in symbols}

    file_ids = {s.file_id for s in symbols if s.file_id}
    path_by_file: dict[str, str] = {}
    for fid in file_ids:
        f = db.get_file(fid)
        if f is not None:
            path_by_file[fid] = f.path

    def label(sid: str) -> str:
        sym = by_id.get(sid)
        if sym is None:
            return sid
        path = path_by_file.get(sym.file_id, "?") if sym.file_id else "?"
        name = sym.display_name or "?"
        return f"{name} ({path})"

    lines = []
    for src in sorted(subgraph):
        for dst in sorted(subgraph[src]):
            lines.append(f"  {label(src)} -> {label(dst)}")
    return "\n".join(lines)


def _format_file_subgraph(subgraph: dict[str, dict[str, int]]) -> str:
    lines = []
    for src in sorted(subgraph):
        for dst, weight in sorted(subgraph[src].items()):
            lines.append(f"  {src} -> {dst}  (weight {weight})")
    return "\n".join(lines)


def _format_cluster_subgraph(subgraph: dict[str, dict[str, int]]) -> str:
    lines = []
    for src in sorted(subgraph):
        for dst, weight in sorted(subgraph[src].items()):
            lines.append(f"  {src} -> {dst}  (weight {weight})")
    return "\n".join(lines)


def _is_python_import_line(line: str) -> bool:
    return _PY_IMPORT_LINE_RE.match(line) is not None


def _is_python_reexport_file(language: str | None, contents: str | None) -> bool:
    if language != "python" or not contents:
        return False
    non_blank = [l for l in contents.splitlines() if l.strip()]
    if len(non_blank) < _PY_REEXPORT_MIN_LINES:
        return False
    imports = sum(1 for l in non_blank if _is_python_import_line(l))
    return imports / len(non_blank) >= _PY_REEXPORT_THRESHOLD


def _render_with_gutter(contents: str) -> str:
    lines = contents.splitlines()
    if not lines:
        return ""
    width = max(4, len(str(len(lines))))
    return "\n".join(f"{i + 1:>{width}}| {line}" for i, line in enumerate(lines))


def _format_files_full(db: RepoDB, cluster_id: str) -> str:
    parts = []
    for file in sorted(db.files_in_cluster(cluster_id), key=lambda f: f.path):
        if file.contents is None or not file.contents.strip():
            continue
        display_path = file.path.replace("\\", "/")
        if _is_python_reexport_file(file.language, file.contents):
            parts.append(
                f"=== {display_path} ===\n"
                "# Pure re-export module: not citable. The actual implementations "
                "live in the other files in this cluster."
            )
            continue
        gutter = _render_with_gutter(file.contents)
        parts.append(f"=== {display_path} ===\n{gutter}")
    return "\n\n".join(parts)


def _format_file_summaries(
    db: RepoDB, subgraph: dict[str, dict[str, int]]
) -> str:
    file_ids: set[str] = set(subgraph.keys())
    for targets in subgraph.values():
        file_ids.update(targets.keys())
    parts = []
    for fid in sorted(file_ids):
        file = db.get_file(fid)
        if file is None or not file.summary:
            continue
        parts.append(f"=== {file.path} ===\n{file.summary}")
    return "\n\n".join(parts)


def _format_cluster_summaries(
    db: RepoDB, subgraph: dict[str, dict[str, int]]
) -> str:
    cluster_ids: set[str] = set(subgraph.keys())
    for targets in subgraph.values():
        cluster_ids.update(targets.keys())
    parts = []
    for cid in sorted(cluster_ids):
        sub = db.get_cluster(cid)
        if sub is None or not sub.summary:
            continue
        parts.append(f"=== {cid} ===\n{sub.summary}")
    return "\n\n".join(parts)


def _parse_citation(
    cite: str, valid_paths: set[str], file_line_counts: dict[str, int]
) -> tuple[str, int, int] | None:
    """Parse `path:N` / `path:N-M`. Returns (path, start, end) or None on any
    egregious failure (bad shape, unknown path, out-of-range, end < start).
    """
    if not isinstance(cite, str):
        return None
    m = _CITATION_RE.match(cite.strip())
    if not m:
        return None
    path = m.group(1).replace("\\", "/")
    if path not in valid_paths:
        return None
    start = int(m.group(2))
    end = int(m.group(3)) if m.group(3) else start
    if end < start:
        return None
    line_count = file_line_counts.get(path)
    if line_count is not None and (start < 1 or end > line_count):
        return None
    return path, start, end


def _validate_citations(
    citations,
    valid_paths: set[str],
    file_line_counts: dict[str, int],
) -> bool:
    """Cheap egregious-only check: shape, path-exists, line-in-range.

    Anything subtler (cited line is an import, file is a re-export, etc.) is
    handled by the prompt - we don't drop questions for that.
    """
    if not isinstance(citations, list) or not citations:
        return False
    for cite in citations:
        if _parse_citation(cite, valid_paths, file_line_counts) is None:
            return False
    return True


def _validate_highlight_payload(
    payload: dict,
    valid_paths: set[str],
    file_line_counts: dict[str, int],
) -> bool:
    """Highlight-specific egregious check: block + correct are well-formed
    citations, all on the same file, and every `correct` range lies inside
    `block`'s range. Subtler quality (criterion is sharp, subset is small) is
    the prompt's job.
    """
    block = payload.get("block")
    correct = payload.get("correct")
    if not isinstance(block, str) or not isinstance(correct, list) or not correct:
        return False
    parsed_block = _parse_citation(block, valid_paths, file_line_counts)
    if parsed_block is None:
        return False
    block_path, block_start, block_end = parsed_block
    for c in correct:
        parsed = _parse_citation(c, valid_paths, file_line_counts)
        if parsed is None:
            return False
        c_path, c_start, c_end = parsed
        if c_path != block_path:
            return False
        if c_start < block_start or c_end > block_end:
            return False
    return True


def _build_problem(
    cluster_id: str,
    kind: str,
    payload: dict,
    valid_paths: set[str],
    file_line_counts: dict[str, int],
    require_citations: bool,
) -> Problem | None:
    try:
        if require_citations:
            if not _validate_citations(
                payload.get("citations"), valid_paths, file_line_counts
            ):
                return None
            if kind == "Highlight" and not _validate_highlight_payload(
                payload, valid_paths, file_line_counts
            ):
                return None
            citations = list(payload["citations"])
        else:
            citations = []
        enriched = {
            **payload,
            "citations": citations,
            "problem_id": str(uuid.uuid4()),
            "concept_id": cluster_id,
            "concept_group_id": None,
        }
        return ProblemFactory.create(kind, enriched)
    except (KeyError, TypeError, ValueError, IndexError):
        return None


def _call_llm(client: OpenAIClient, prompt: str, schema: dict) -> dict:
    try:
        response = client.generate_json(prompt, schema=schema)
    except Exception as exc:
        print(f"[generate_questions] LLM call failed: {exc}")
        return {}
    return response if isinstance(response, dict) else {}


def _hash_job(prompt: str, schema: dict) -> str:
    canonical = prompt + "\n---\n" + json.dumps(schema, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _cache_path(cache_key: str) -> Path:
    return _CACHE_DIR / cache_key / _CACHE_NAME


def _load_cache(cache_key: str) -> dict[str, dict]:
    path = _cache_path(cache_key)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _save_cache(cache: dict[str, dict], cache_key: str) -> None:
    path = _cache_path(cache_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, indent=2), encoding="utf-8")
