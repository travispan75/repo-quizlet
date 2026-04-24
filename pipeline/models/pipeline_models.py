from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from pipeline.scip.proto.scip_pb2 import Document, Occurrence as ScipOccurrence, SymbolInformation


SYMBOL_ROLE_DEFINITION = 1
SYMBOL_ROLE_IMPORT = 2
SYMBOL_ROLE_READ_ACCESS = 8
SYMBOL_ROLE_WRITE_ACCESS = 4


@dataclass(slots=True, frozen=True)
class Symbol:
    symbol_id: str
    display_name: str
    kind: str
    language: str
    enclosing_symbol_id: str | None = None
    signature: str | None = None
    documentation: str | None = None

    @classmethod
    def from_symbol_information(
        cls,
        symbol_info: SymbolInformation,
        document: Document,
    ) -> Symbol:
        signature = None
        if symbol_info.HasField("signature_documentation"):
            signature = symbol_info.signature_documentation.text or None

        documentation = "\n".join(symbol_info.documentation).strip() or None

        return cls(
            symbol_id=symbol_info.symbol,
            display_name=symbol_info.display_name,
            kind=SymbolInformation.Kind.Name(symbol_info.kind),
            language=document.language,
            enclosing_symbol_id=symbol_info.enclosing_symbol or None,
            signature=signature,
            documentation=documentation,
        )


@dataclass(slots=True, frozen=True)
class Occurrence:
    occurrence_id: str
    symbol_id: str
    file_path: str
    start_line: int
    start_character: int
    end_line: int
    end_character: int
    role_flags: int
    is_definition: bool
    is_reference: bool
    is_import: bool
    enclosing_symbol_id: str | None = None

    @staticmethod
    def build_occurrence_id(
        *,
        file_path: str,
        symbol_id: str,
        start_line: int,
        start_character: int,
        end_line: int,
        end_character: int,
        role_flags: int,
    ) -> str:
        return (
            f"{file_path}:{start_line}:{start_character}:{end_line}:{end_character}:"
            f"{role_flags}:{symbol_id}"
        )

    @classmethod
    def from_occurrence(
        cls,
        occurrence: ScipOccurrence,
        document: Document,
        enclosing_symbol_id: str | None = None,
    ) -> Occurrence:
        start_line, start_character, end_line, end_character = _normalize_range(occurrence.range)
        file_path = document.relative_path
        role_flags = occurrence.symbol_roles
        is_definition = bool(role_flags & SYMBOL_ROLE_DEFINITION)
        is_import = bool(role_flags & SYMBOL_ROLE_IMPORT)
        is_reference = not is_definition and bool(
            role_flags & (SYMBOL_ROLE_READ_ACCESS | SYMBOL_ROLE_WRITE_ACCESS | SYMBOL_ROLE_IMPORT)
        )

        return cls(
            occurrence_id=cls.build_occurrence_id(
                file_path=file_path,
                symbol_id=occurrence.symbol,
                start_line=start_line,
                start_character=start_character,
                end_line=end_line,
                end_character=end_character,
                role_flags=role_flags,
            ),
            symbol_id=occurrence.symbol,
            file_path=file_path,
            start_line=start_line,
            start_character=start_character,
            end_line=end_line,
            end_character=end_character,
            role_flags=role_flags,
            is_definition=is_definition,
            is_reference=is_reference,
            is_import=is_import,
            enclosing_symbol_id=enclosing_symbol_id,
        )

    @classmethod
    def from_document(cls, document: Document) -> list[Occurrence]:
        definitions = [
            occurrence
            for occurrence in document.occurrences
            if occurrence.symbol and occurrence.symbol_roles & SYMBOL_ROLE_DEFINITION
        ]

        occurrences: list[Occurrence] = []
        for occurrence in document.occurrences:
            enclosing_symbol_id = _find_nearest_enclosing_definition(occurrence, definitions)
            occurrences.append(
                cls.from_occurrence(
                    occurrence=occurrence,
                    document=document,
                    enclosing_symbol_id=enclosing_symbol_id,
                )
            )
        return occurrences


@dataclass(slots=True, frozen=True)
class File:
    file_path: str
    language: str

    @classmethod
    def from_document(cls, document: Document) -> File:
        return cls(
            file_path=document.relative_path,
            language=document.language,
        )

def _normalize_range(raw_range: Iterable[int]) -> tuple[int, int, int, int]:
    values = tuple(raw_range)
    if len(values) == 3:
        start_line, start_character, end_character = values
        return start_line, start_character, start_line, end_character
    if len(values) == 4:
        return values
    raise ValueError(f"Unsupported SCIP range length: {len(values)}")


def _find_nearest_enclosing_definition(
    target: ScipOccurrence,
    definitions: Iterable[ScipOccurrence],
) -> str | None:
    target_range = _normalize_range(target.range)
    best_symbol_id: str | None = None
    best_span: tuple[int, int, int, int] | None = None

    for definition in definitions:
        if definition is target or not definition.symbol:
            continue

        definition_range = _normalize_range(definition.range)
        if not _contains(definition_range, target_range):
            continue

        if best_span is None or _is_more_specific(definition_range, best_span):
            best_span = definition_range
            best_symbol_id = definition.symbol

    return best_symbol_id


def _contains(outer: tuple[int, int, int, int], inner: tuple[int, int, int, int]) -> bool:
    return (outer[0], outer[1]) <= (inner[0], inner[1]) and (outer[2], outer[3]) >= (inner[2], inner[3])


def _is_more_specific(
    candidate: tuple[int, int, int, int],
    current: tuple[int, int, int, int],
) -> bool:
    return (candidate[0], candidate[1], -candidate[2], -candidate[3]) > (
        current[0],
        current[1],
        -current[2],
        -current[3],
    )


@dataclass(slots=True, frozen=True)
class Chunk:
    symbol_id: str
    name: str
    file: str
    start_line: int
    end_line: int
    code: str
    calls: frozenset[str] = frozenset()
    called_by: frozenset[str] = frozenset()
    embedding: list[float] | None = None
