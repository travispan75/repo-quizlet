import hashlib
import json
from pathlib import Path
from typing import ClassVar

from pipeline.context import State
from pipeline.core.llm import OpenAIClient
from pipeline.core.base_stage import BaseStage
from pipeline.context.stages.summarize_clusters import SummarizeClusters


_PROMPT_TOKEN_BUDGET = 6000
_README_TOKEN_CAP = 2500
_MIN_SUMMARY_BUDGET = 1500
_CACHE_DIR = Path(__file__).resolve().parents[1] / ".cache"
_CACHE_NAME = "repo_summaries.json"

_REPO_PROMPT = """You are summarizing an entire codebase.

You may receive two kinds of input below:
- A README (optional - present only when the section appears below). When present, use it for stated intent and high-level description. If the README's claims conflict with what the cluster summaries describe, PREFER THE CLUSTER SUMMARIES (they describe what the code actually does, while READMEs sometimes overstate or describe aspirations).
- Cluster summaries (always present). Each describes a cohesive group of code in the repo. Use these for actual architecture and capabilities.

Write a 4-8 sentence summary (one to two paragraphs) covering:
- What this repository is and what it does at a high level
- Its overall architecture - the main subsystems and how they relate
- Its main components or capabilities

Output rules:
- Prefer concrete, specific language over generic marketing phrases.
- Do not start with "this repo", "this project", "this codebase", "this library", "this application", "this software", or "this package".
- Output flowing prose only - no bullet points, no markdown, no headings.

{readme_section}CLUSTER SUMMARIES:
{summaries}

REPO SUMMARY:"""

_PARTIAL_PROMPT = """Below are cluster summaries from a portion of a larger repository. Your output will later be combined with other portions to produce the full repo summary.

Write a 3-5 sentence synthesis describing what this set of clusters does together architecturally. SYNTHESIZE - do not enumerate the cluster summaries one by one.

Output rules:
- Do not write linking phrases such as "additionally", "moreover", "furthermore", "in summary", or "overall" - your output is a fragment, not a standalone conclusion.
- Do not start with "this slice", "this portion", "this set", "this group", or "this code".
- Output flowing prose only - no bullet points, no markdown, no headings.

CLUSTER SUMMARIES:
{summaries}

SYNTHESIS:"""


class SummarizeRepo(BaseStage):
    depends_on: ClassVar[tuple[type["BaseStage"], ...]] = (SummarizeClusters,)

    def run(self, ctx: State) -> None:
        if not ctx.graph_clusters:
            return

        top_layer = ctx.graph_clusters[-1]
        cluster_summaries = sorted(
            cluster.summary
            for cluster in top_layer.values()
            if cluster.summary is not None
        )
        if not cluster_summaries:
            return
        readme = ctx.readme
        if readme is not None:
            readme = _truncate(readme, _README_TOKEN_CAP)

        prompt_hash = _hash_inputs(readme, cluster_summaries)
        cache = _load_cache(ctx.cache_key)

        if prompt_hash not in cache:
            client = OpenAIClient()

            readme_tokens = _approx_tokens(readme) if readme else 0
            summary_budget = max(
                _MIN_SUMMARY_BUDGET,
                _PROMPT_TOKEN_BUDGET - readme_tokens,
            )
            reduced = _reduce_summaries(client, cluster_summaries, summary_budget)

            prompt = _REPO_PROMPT.format(
                readme_section=_format_readme_section(readme),
                summaries=_format_summaries(reduced),
            )
            cache[prompt_hash] = client.generate(prompt)

        ctx.repo_summary = cache[prompt_hash]
        _save_cache({prompt_hash: cache[prompt_hash]}, ctx.cache_key)


def _format_readme_section(readme: str | None) -> str:
    if not readme:
        return ""
    return f"README:\n{readme}\n\n"


def _truncate(text: str, max_tokens: int) -> str:
    if _approx_tokens(text) <= max_tokens:
        return text
    return text[: max_tokens * 4]


def _reduce_summaries(
    client: OpenAIClient,
    summaries: list[str],
    budget: int,
) -> list[str]:
    while True:
        if _approx_tokens(_format_summaries(summaries)) <= budget:
            return summaries
        batches = _pack_summaries(summaries, budget)
        if len(batches) <= 1:
            return summaries
        summaries = [
            client.generate(_PARTIAL_PROMPT.format(summaries=_format_summaries(batch)))
            for batch in batches
        ]


def _format_summaries(summaries: list[str]) -> str:
    return "\n".join(f"- {s}" for s in summaries)


def _pack_summaries(summaries: list[str], budget: int) -> list[list[str]]:
    batches: list[list[str]] = []
    current: list[str] = []
    current_tokens = 0
    for s in summaries:
        n = _approx_tokens(s)
        if current and current_tokens + n > budget:
            batches.append(current)
            current = []
            current_tokens = 0
        current.append(s)
        current_tokens += n
    if current:
        batches.append(current)
    return batches


def _approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _hash_inputs(readme: str | None, summaries: list[str]) -> str:
    parts = [readme or ""] + sorted(summaries)
    return hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()


def _cache_path(cache_key: str) -> Path:
    return _CACHE_DIR / cache_key / _CACHE_NAME


def _load_cache(cache_key: str) -> dict[str, str]:
    path = _cache_path(cache_key)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _save_cache(cache: dict[str, str], cache_key: str) -> None:
    path = _cache_path(cache_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, indent=2), encoding="utf-8")
