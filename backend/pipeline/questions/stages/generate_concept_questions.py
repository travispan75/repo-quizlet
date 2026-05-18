from __future__ import annotations

import json
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import ClassVar

from tqdm import tqdm

from pipeline.core.base_stage import BaseStage
from pipeline.core.llm import OpenAIClient
from pipeline.questions.db import ConceptGroup, File, RepoDB
from pipeline.questions.models.pipeline_models import Problem, ProblemFactory
from pipeline.questions.state import QuestionState
from pipeline.questions.stages.generate_questions import _call_llm, _hash_job


_MAX_WORKERS = 16
_CACHE_DIR = Path(__file__).resolve().parents[1] / ".cache"
_CACHE_NAME = "concept_questions.json"
_MAX_QUESTIONS_PER_GROUP = 2


def _str() -> dict:
    return {"type": "string"}


def _str_array(min_items: int, max_items: int) -> dict:
    return {
        "type": "array",
        "items": _str(),
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


_ITEM_SCHEMAS = {
    "MCQ": _obj({
        "prompt": _str(),
        "explanation": _str(),
        "correct": _str(),
        "distractors": _str_array(3, 3),
    }),
    "TF": _obj({
        "prompt": _str(),
        "explanation": _str(),
        "is_true": {"type": "boolean"},
    }),
}


_RESPONSE_SCHEMA = {
    "name": "concept_questions",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["MCQ", "TF"],
        "properties": {
            "MCQ": {
                "type": "array",
                "items": _ITEM_SCHEMAS["MCQ"],
                "maxItems": _MAX_QUESTIONS_PER_GROUP,
            },
            "TF": {
                "type": "array",
                "items": _ITEM_SCHEMAS["TF"],
                "maxItems": _MAX_QUESTIONS_PER_GROUP,
            },
        },
    },
}


_PROMPT_TEMPLATE = """You are creating quiz questions about a CROSS-CUTTING CONCEPT that appears across multiple unrelated parts of this codebase.

CONCEPT: "{label}"
{variants_line}This concept shows up in {n_files} files spanning {n_clusters} different modules/clusters of the codebase.

FILES WHERE THIS CONCEPT APPEARS:
{files_block}

ABSOLUTE RULES (violating any is a failure):
- GROUNDING: Use only what is in the summaries above. Do not invent files, classes, behaviors, or library specifics not present.
- CROSS-CUTTING ONLY: Generate questions that DEPEND on the fact that this concept appears in MULTIPLE places. A question answerable from a single file or a single cluster is a failure - that belongs to per-cluster questions.
- NO TEXTBOOK TRIVIA: Reject "what is the {label}?" or generic pattern-definition questions. The question must be about how THIS CODEBASE specifically applies {label}, what's consistent or different between the occurrences, and the consequences.
- NO TRIVIAL NAME-LOOKUP: Reject "which files use {label}?" - that is a directory listing, not understanding.
- CANONICAL OUTPUT: Do NOT scramble - the frontend randomizes. Truth goes in its schema-designated field.

GOOD QUESTION PATTERNS:
- "Why does this codebase apply {label} in BOTH {file_a} and {file_b} rather than direct construction in one of them?"
- "Which of these uses of {label} is the most idiomatic example of the pattern as applied here?"
- "What common motivation links the use of {label} across these files?"
- "If you removed the {label} from {file_a}, what consequence would propagate through the way the other files use the same concept?"

OUTPUT KINDS:
- MCQ (up to {cap}): `correct` is the answer, `distractors` is 3 plausible-but-wrong options.
- TF (up to {cap}): `prompt` is a POSITIVE DECLARATIVE CLAIM about how this codebase applies {label} (no "not", no "never", no question marks). `is_true` is the truth value.

If the concept evidence here is too thin to support a real cross-cutting question, return EMPTY arrays. Quality > quantity. At most {cap} questions total combined.

OUTPUT: JSON object with `MCQ` and `TF` arrays. Field shapes are schema-enforced."""


class GenerateConceptQuestions(BaseStage):
    depends_on: ClassVar[tuple[type["BaseStage"], ...]] = ()

    def run(self, ctx: QuestionState) -> None:
        groups = ctx.db.all_concept_groups()
        if not groups:
            return

        cluster_by_file = _cluster_by_file(ctx.db)

        client = OpenAIClient()
        cache = _load_cache(ctx.cache_key)
        used_hashes: set[str] = set()

        jobs: list[tuple[ConceptGroup, str, str]] = []
        for group in groups:
            files = ctx.db.files_by_paths(group.file_paths)
            if not files:
                continue
            prompt = _build_prompt(group, files, cluster_by_file)
            job_hash = _hash_job(prompt, _RESPONSE_SCHEMA)
            used_hashes.add(job_hash)
            jobs.append((group, prompt, job_hash))

        pending = [j for j in jobs if j[2] not in cache]
        if pending:
            with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as ex:
                futures = {
                    ex.submit(_call_llm, client, prompt, _RESPONSE_SCHEMA): (group, job_hash)
                    for group, prompt, job_hash in pending
                }
                total = len(futures)
                for i, fut in enumerate(
                    tqdm(
                        as_completed(futures),
                        total=total,
                        desc="generate concept questions",
                    ),
                    start=1,
                ):
                    _, job_hash = futures[fut]
                    cache[job_hash] = fut.result()
                    ctx.progress.heartbeat(i, total)
            _save_cache(cache, ctx.cache_key)

        for group, _prompt, job_hash in jobs:
            payload = cache.get(job_hash)
            if not isinstance(payload, dict):
                continue
            for kind, items in payload.items():
                if not isinstance(items, list):
                    continue
                for item in items:
                    problem = _build_concept_problem(group, kind, item)
                    if problem is not None:
                        ctx.problems.append(problem)

        cache = {h: v for h, v in cache.items() if h in used_hashes}
        _save_cache(cache, ctx.cache_key)


def _cluster_by_file(db: RepoDB) -> dict[str, str]:
    return {f.path: f.cluster_id for f in db.all_files() if f.cluster_id}


def _build_prompt(
    group: ConceptGroup,
    files: list[File],
    cluster_by_file: dict[str, str],
) -> str:
    other_tags = [t for t in group.member_tags if t != group.label]
    if other_tags:
        variants = ", ".join(f'"{t}"' for t in other_tags)
        variants_line = f"(Also tagged in this repo as: {variants}.)\n"
    else:
        variants_line = ""

    clusters = {cluster_by_file.get(f.path) for f in files} - {None}
    files_block = "\n\n".join(_render_file_block(f) for f in files if f.summary)

    file_a, file_b = (files[0].path, files[1].path if len(files) > 1 else files[0].path)

    return _PROMPT_TEMPLATE.format(
        label=group.label,
        variants_line=variants_line,
        n_files=len(files),
        n_clusters=len(clusters) or 1,
        files_block=files_block,
        file_a=file_a,
        file_b=file_b,
        cap=_MAX_QUESTIONS_PER_GROUP,
    )


def _render_file_block(file: File) -> str:
    tag_line = ""
    if file.concepts:
        tag_line = f" [tags: {', '.join(file.concepts)}]"
    return f"=== {file.path}{tag_line} ===\n{file.summary}"


def _build_concept_problem(
    group: ConceptGroup,
    kind: str,
    payload: dict,
) -> Problem | None:
    if kind not in ("MCQ", "TF"):
        return None
    try:
        enriched = {
            **payload,
            "citations": [],
            "problem_id": str(uuid.uuid4()),
            "concept_id": None,
            "concept_group_id": group.id,
        }
        return ProblemFactory.create(kind, enriched)
    except (KeyError, TypeError, ValueError, IndexError):
        return None


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
