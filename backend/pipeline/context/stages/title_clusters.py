from __future__ import annotations

import dataclasses
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import ClassVar

from tqdm import tqdm

from pipeline.context import State
from pipeline.context.models import Cluster
from pipeline.context.stages.summarize_clusters import SummarizeClusters
from pipeline.core.base_stage import BaseStage
from pipeline.core.llm import OpenAIClient


_MAX_WORKERS = 16
_CACHE_DIR = Path(__file__).resolve().parents[1] / ".cache"
_CACHE_NAME = "cluster_titles.json"

_LEVEL_HINTS = {
    0: (
        "Level 0 is the FINEST grain (small groups of tightly-coupled files). "
        "Titles should name a SPECIFIC area of knowledge embodied by those files."
    ),
    1: (
        "Level 1 aggregates several level-0 clusters. Titles should name the "
        "broader subject area that unifies the sub-clusters."
    ),
}
_LEVEL_HINT_DEFAULT = (
    "Higher levels are ARCHITECTURAL aggregations. Titles should name the "
    "subsystem-level subject area at that altitude."
)

_PROMPT_TEMPLATE = """You are labeling clusters of related code so that learners can browse a codebase by topic. Below are all clusters at LEVEL {level} of a hierarchical clustering of the {repo_name} repository, each with a 3-5 sentence summary.

{level_hint}

For EACH cluster, output a CONCEPT NAME — a short noun phrase that names an AREA OF KNOWLEDGE within this codebase. Think "what would the chapter heading be in a textbook covering this code?". These names appear in the UI as topic labels (e.g., "You've mastered 5/10 questions in <name>").

ABSOLUTE RULES:
- 2-5 words. Title Case. Prefer the SHORTEST title that is still ACCURATE and DISTINCTIVE — accuracy matters more than brevity.
- Noun phrase only. NEVER a sentence, NEVER an imperative.
- Do NOT begin with "The".
- Do NOT include the word "{repo_name}" anywhere in the title — the project context is already implicit. (E.g., for a Flask repo, "Flask Routing" is REJECTED; "Routing & Dispatch" is ACCEPTED.)
- Names must read like a SUBJECT AREA / textbook chapter heading, NOT the name of a tool, product, file, or function. (E.g., "Templating Engine" sounds like a tool — prefer "Template Rendering".)
- Each title must be MEANINGFULLY different from its siblings at this level. If a reader saw only the titles (no summaries), they should still be able to tell the clusters apart.

REJECTED examples (vague, generic, low information density — these tell the reader nothing):
- "Core Features"
- "Application Management"
- "Web Framework Core"
- "Modular Framework"
- "Core Components"
- "General Functionality"
- "Application Logic"
- "Various Modules"
- "Helper Functions" / "Utility Code" / "Misc"
- Any title that includes "{repo_name}" anywhere.

ACCEPTED examples (each names a concrete area of knowledge):
- "Request Routing & Dispatch"
- "Application Context Lifecycle"
- "Template Rendering"
- "Session Management"
- "Signal Handling"
- "Blueprint Composition"
- "Database Connection Pooling"
- "CLI Commands"
- "Error Handling Patterns"

OUTPUT: one entry per input cluster, using the EXACT cluster_id given.

CLUSTERS:
{clusters_block}
"""

_RESPONSE_SCHEMA = {
    "name": "cluster_titles",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["titles"],
        "properties": {
            "titles": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["cluster_id", "title"],
                    "properties": {
                        "cluster_id": {"type": "string"},
                        "title": {"type": "string"},
                    },
                },
            },
        },
    },
}


class TitleClusters(BaseStage):
    depends_on: ClassVar[tuple[type["BaseStage"], ...]] = (SummarizeClusters,)

    def run(self, ctx: State) -> None:
        if not ctx.graph_clusters:
            return

        client = OpenAIClient()
        cache = _load_cache(ctx.cache_key)
        used_hashes: set[str] = set()
        repo_name = ctx.repo_name or "this project"

        jobs: list[tuple[int, dict[str, Cluster], str, str]] = []
        for layer_idx, layer in enumerate(ctx.graph_clusters):
            entries = sorted(
                (cid, cluster.summary)
                for cid, cluster in layer.items()
                if cluster.summary
            )
            if not entries:
                continue
            prompt = _build_prompt(layer_idx, entries, repo_name)
            job_hash = _hash_job(prompt)
            used_hashes.add(job_hash)
            jobs.append((layer_idx, layer, prompt, job_hash))

        pending = [j for j in jobs if j[3] not in cache]
        if pending:
            with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as ex:
                futures = {
                    ex.submit(_call_llm, client, prompt): (layer_idx, job_hash)
                    for layer_idx, _layer, prompt, job_hash in pending
                }
                for fut in tqdm(
                    as_completed(futures),
                    total=len(futures),
                    desc="title clusters",
                ):
                    layer_idx, job_hash = futures[fut]
                    cache[job_hash] = fut.result()
            _save_cache(cache, ctx.cache_key)

        for layer_idx, layer, _prompt, job_hash in jobs:
            payload = cache.get(job_hash) or {}
            titles_by_id = {
                str(item["cluster_id"]): str(item["title"]).strip()
                for item in payload.get("titles", [])
                if isinstance(item, dict)
                and "cluster_id" in item
                and "title" in item
            }
            updated: dict[str, Cluster] = {}
            for cid, cluster in layer.items():
                title = titles_by_id.get(cid) or None
                updated[cid] = dataclasses.replace(cluster, title=title)
            ctx.graph_clusters[layer_idx] = updated

        cache = {h: v for h, v in cache.items() if h in used_hashes}
        _save_cache(cache, ctx.cache_key)


def _build_prompt(
    level: int, entries: list[tuple[str, str]], repo_name: str
) -> str:
    clusters_block = "\n\n".join(
        f"--- {cid} ---\n{summary}" for cid, summary in entries
    )
    return _PROMPT_TEMPLATE.format(
        level=level,
        repo_name=repo_name,
        level_hint=_LEVEL_HINTS.get(level, _LEVEL_HINT_DEFAULT),
        clusters_block=clusters_block,
    )


def _call_llm(client: OpenAIClient, prompt: str) -> dict:
    try:
        response = client.generate_json(prompt, schema=_RESPONSE_SCHEMA)
    except Exception as exc:
        print(f"[title_clusters] LLM call failed: {exc}")
        return {}
    return response if isinstance(response, dict) else {}


def _hash_job(prompt: str) -> str:
    canonical = prompt + "\n---\n" + json.dumps(_RESPONSE_SCHEMA, sort_keys=True)
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
