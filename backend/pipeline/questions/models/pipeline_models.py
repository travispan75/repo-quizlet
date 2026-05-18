from __future__ import annotations

from abc import ABC
from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class Problem(ABC):
    problem_id: str
    concept_id: str | None
    concept_group_id: str | None
    prompt: str
    explanation: str
    citations: list[str]


@dataclass(slots=True, frozen=True)
class MCQ(Problem):
    correct: str
    distractors: list[str]


@dataclass(slots=True, frozen=True)
class TF(Problem):
    is_true: bool


@dataclass(slots=True, frozen=True)
class MultipleSelect(Problem):
    correct: list[str]
    distractors: list[str]


@dataclass(slots=True, frozen=True)
class Order(Problem):
    correct_order: list[str]


@dataclass(slots=True, frozen=True)
class Pairing(Problem):
    pairs: list[tuple[str, str]]


@dataclass(slots=True, frozen=True)
class Highlight(Problem):
    block: str
    correct: list[str]


class ProblemFactory:
    @staticmethod
    def create(kind: str, payload: dict) -> Problem:
        common = {
            "problem_id": payload["problem_id"],
            "concept_id": payload["concept_id"],
            "prompt": payload["prompt"],
            "explanation": payload["explanation"],
            "citations": list(payload["citations"]),
            "concept_group_id": payload.get("concept_group_id"),
        }
        match kind:
            case "MCQ":
                return MCQ(
                    **common,
                    correct=str(payload["correct"]),
                    distractors=list(payload["distractors"]),
                )
            case "TF":
                return TF(
                    **common,
                    is_true=bool(payload["is_true"]),
                )
            case "MultipleSelect":
                return MultipleSelect(
                    **common,
                    correct=list(payload["correct"]),
                    distractors=list(payload["distractors"]),
                )
            case "Order":
                return Order(
                    **common,
                    correct_order=list(payload["correct_order"]),
                )
            case "Pairing":
                return Pairing(
                    **common,
                    pairs=[(str(p[0]), str(p[1])) for p in payload["pairs"]],
                )
            case "Highlight":
                return Highlight(
                    **common,
                    block=str(payload["block"]),
                    correct=list(payload["correct"]),
                )
            case _:
                raise ValueError(f"Unknown problem kind: {kind!r}")
