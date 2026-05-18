from __future__ import annotations

import json
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import ClassVar

from tqdm import tqdm

from pipeline.core.base_stage import BaseStage
from pipeline.core.llm import OpenAIClient
from pipeline.questions.db import Cluster
from pipeline.questions.state import QuestionState
from pipeline.questions.stages.generate_questions import (
    _build_problem,
    _call_llm,
    _hash_job,
    _make_item_schemas,
    _render_cluster,
)


_MAX_WORKERS = 16
_CACHE_DIR = Path(__file__).resolve().parents[1] / ".cache"
_CACHE_NAME = "hypotheticals.json"

# Per-cluster cap is chosen adaptively so a small repo (few L0 clusters) gets
# more hypotheticals per cluster, and a large repo gets fewer. The product
# loosely targets ~15-20 hypotheticals total.
_TARGET_TOTAL = 18
_MIN_CAP = 2
_MAX_CAP = 6


_CITATIONS_RULE = """
- CITATIONS: Every question MUST cite 1-3 source locations in `citations`. Each citation is the EXACT string `path/to/file.py:N` or `path/to/file.py:N-M` where:
    * `path/to/file.py` is one of the `=== ... ===` filenames shown above. Copy it verbatim.
    * `N` and `M` are line numbers read DIRECTLY from the `   N| ` gutter on the left of that file's source. Do NOT guess. Do NOT count.
    * Cite the lines that DEMONSTRATE the convention, precedent, or dependency the answer relies on. Do NOT cite import lines, blank lines, comment-only lines, or files marked `Pure re-export module: not citable.`"""


_PER_KIND_SEMANTICS: dict[str, str] = {
    "MCQ":
        "`correct` is the option most consistent with patterns visible in this cluster; "
        "3 `distractors` are plausible alternatives that VIOLATE those patterns. "
        "GOOD: 'If you added a new background-task helper, where would it go to match "
        "the existing layout?' (correct = the dir/module pattern shown; distractors = "
        "other plausible-but-inconsistent placements). "
        "REJECTED: 'Which Python web framework is best for X?' (not grounded in cluster).",
    "TF":
        "`prompt` MUST be a POSITIVE DECLARATIVE CLAIM about a hypothetical change "
        "to this cluster's code. Two hard rules: (1) NEVER interrogative - no "
        "'which', 'where', 'what is the correct order' (those go in MCQ/Order). "
        "(2) NEVER negate the claim itself - no 'not', 'no', 'doesn't', 'won't', "
        "'wouldn't' in the prompt. Phrase as a POSITIVE assertion and use `is_true` "
        "to mark whether it holds. The `explanation` MUST argue for the same answer "
        "you put in `is_true`. "
        "GOOD: 'Removing the `app.app_context()` wrapper from `cli.py:42-47` would "
        "cause `current_app` lookups in the wrapped command to raise.' (positive; "
        "is_true=true). "
        "REJECTED: 'Changing the default logging level will NOT affect existing "
        "functionality.' (negative phrasing - rewrite as 'Changing the default "
        "logging level WILL affect existing functionality' and set is_true=true). "
        "REJECTED: 'If you wanted to add a new route, which existing function's "
        "structure would you follow?' (interrogative - has no T/F answer; use MCQ "
        "for which-questions). "
        "REJECTED: 'It is generally a good idea to use context managers.' (not "
        "grounded in this cluster).",
    "MultipleSelect":
        "`correct` lists 2-4 changes that are ALL required to consistently make a "
        "hypothetical edit; `distractors` are 2-3 changes that look related but the "
        "source shows are NOT required. Use only when an edit-shape from the cluster "
        "makes multiple changes simultaneously needed.",
    "Order":
        "`correct_order` is 3-6 concrete edit/refactor steps in the order the existing "
        "dependency structure forces. "
        "GOOD: 'You want to extract `get_db` into its own module without breaking "
        "imports - what is the correct order of edits?' "
        "REJECTED: generic abstractions like 'design -> implement -> test'.",
    "Pairing":
        "3-5 `[hypothetical_change, concrete_consequence]` pairs. Right side names a "
        "SPECIFIC consequence visible from the source - never a restatement of the change. "
        "GOOD: ['Rename `current_app` -> `cur_app` repo-wide', 'Every "
        "`from flask import current_app` site and the `flask/globals.py` LocalProxy line "
        "break; the re-export in `__init__.py` must update too']. "
        "REJECTED: ['Rename X', 'X gets renamed'] (restatement).",
    "Highlight":
        "`block` and `correct` are STRINGS in the SAME `path/to/file.py:N-M` format as "
        "`citations` - NEVER snippet text or identifiers. "
        "Use for 'where would you make this change?' style questions. "
        "GOOD: 'If you were adding input validation to this view, which lines would be "
        "the right insertion point?' - `block` = the view function's range; `correct` = "
        "1-2 short ranges between argument parsing and main logic. "
        "REJECTED criterion: 'Which lines define the function?' (whole block).",
}


_PROMPT_TEMPLATE = """You are creating CONTRIBUTOR-READINESS questions. A reader has just studied the cluster of code below. Your job is to test whether they could MAKE A CHANGE to this code consistent with the patterns they just read - not whether they can recite what's there.

ABSOLUTE RULES (violating any is a failure):
- GROUNDING: The "right" answer in every question must be derivable from patterns visible in the source below. Do not invent files, modules, libraries, or behaviors not literally present here. If the cluster doesn't show a pattern, do not test that pattern.{citations_rule}
- HYPOTHETICAL FRAMING: Every question must pose a contributor scenario - "if you were adding...", "if you renamed X...", "if X were removed...", "which approach matches the rest of this codebase...", "where would you insert...", "what is the correct order to refactor...". NOT comprehension ("what does X return?") - that is a different stage.
- CANONICAL OUTPUT: Do NOT scramble, rotate, or shuffle - the frontend randomizes. Truth goes in its schema-designated field in canonical order.
- NO TRIVIA: Reject "what is the name of Y", "which of these identifiers exist", and any answer that is a literal restatement of an identifier. The question must depend on this code's specific PATTERNS and CONSEQUENCES, not on generic Python / WSGI / framework knowledge.
- BAR: A reader who could RECITE the code should get it wrong; one who UNDERSTOOD its conventions and dependencies should get it right.
- BUDGET: At most {cap} questions TOTAL for this cluster, distributed across kinds however fits best. Use 0 for any kind that does not fit. If the cluster is thin (bare name declarations, hello-world demo), return EMPTY arrays for ALL kinds. Quality > quantity.

PREFER: extending patterns consistently, what breaks if X changes, where to insert a feature, refactor sequencing, plausible-but-wrong alternatives that violate conventions.

{structure_part}CONTENT:
{content_section}

KINDS:
{kinds_block}

OUTPUT: a JSON object with one field per kind (array of questions). Field shapes are schema-enforced. Total across kinds <= {cap}.
"""


def _format_kinds_block(cap: int) -> str:
    return "\n".join(
        f"- {kind} (up to {cap}): {blurb}"
        for kind, blurb in _PER_KIND_SEMANTICS.items()
    )


def _make_response_schema(cap: int) -> dict:
    item_schemas = _make_item_schemas(include_citations=True)
    return {
        "name": "cluster_hypotheticals",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": list(item_schemas.keys()),
            "properties": {
                kind: {
                    "type": "array",
                    "items": item_schemas[kind],
                    "maxItems": cap,
                }
                for kind in item_schemas
            },
        },
    }


def _build_prompt(rendered: dict[str, str], cap: int) -> str:
    if rendered["subgraph_section"]:
        structure_part = (
            f"STRUCTURE (directed call/dependency edges among real symbols/files in this cluster):\n"
            f"{rendered['subgraph_section']}\n\n"
        )
    else:
        structure_part = ""
    return _PROMPT_TEMPLATE.format(
        citations_rule=_CITATIONS_RULE,
        cap=cap,
        structure_part=structure_part,
        content_section=rendered["content_section"],
        kinds_block=_format_kinds_block(cap),
    )


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


class GenerateHypotheticals(BaseStage):
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

        clusters = ctx.db.clusters_at_level(0)
        if not clusters:
            return

        cap = max(_MIN_CAP, min(_MAX_CAP, math.ceil(_TARGET_TOTAL / len(clusters))))
        schema = _make_response_schema(cap)

        jobs: list[tuple[Cluster, str, str]] = []
        for cluster in clusters:
            rendered = _render_cluster(ctx.db, cluster)
            if rendered is None:
                continue
            prompt = _build_prompt(rendered, cap)
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
                        desc=f"generate hypotheticals (cap {cap})",
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
                        require_citations=True,
                    )
                    if problem is not None:
                        ctx.problems.append(problem)

        cache = {h: v for h, v in cache.items() if h in used_hashes}
        _save_cache(cache, ctx.cache_key)
