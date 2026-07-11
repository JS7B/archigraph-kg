"""Candidate validation and provenance checks for extraction output."""

from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel, ValidationError

from app.extraction.models import (
    CandidateStatus,
    CandidateValidation,
    ChunkExtractionResult,
    EntityCandidate,
    ExtractedEntity,
    ExtractedRelation,
    RelationCandidate,
)
from app.extraction.prompt import ENTITY_TYPES


def _allowed_entity_types() -> set[str]:
    if isinstance(ENTITY_TYPES, str):
        return {item.strip() for item in ENTITY_TYPES.replace(",", "、").split("、") if item.strip()}
    return {str(item).strip() for item in ENTITY_TYPES if str(item).strip()}


def _coerce(model_type: type[BaseModel], value: Any) -> BaseModel:
    if isinstance(value, model_type):
        return value
    if isinstance(value, BaseModel):
        return model_type.model_validate(value.model_dump())
    return model_type.model_validate(value)


def _result(
    candidate: BaseModel | None,
    diagnostics: list[str],
) -> CandidateValidation:
    hard_errors = [item for item in diagnostics if not item.startswith("evidence:")]
    if hard_errors:
        status = CandidateStatus.REJECTED
    elif diagnostics:
        status = CandidateStatus.REVIEW
    else:
        status = CandidateStatus.ACCEPTED
    return CandidateValidation(status=status, diagnostics=diagnostics, candidate=candidate)


def validate_entity_candidate(
    candidate: EntityCandidate | ExtractedEntity | dict[str, Any],
) -> CandidateValidation:
    """Validate one entity candidate without inventing missing provenance."""

    try:
        entity = _coerce(EntityCandidate, candidate)
    except (TypeError, ValidationError, ValueError) as exc:
        return _result(None, [f"candidate: invalid entity payload ({exc})"])

    diagnostics: list[str] = []
    if not entity.name.strip():
        diagnostics.append("name: must not be empty")
    if entity.type not in _allowed_entity_types():
        diagnostics.append(f"type: unknown entity type {entity.type!r}")
    if not 0 <= entity.confidence <= 1:
        diagnostics.append("confidence: must be between 0 and 1")
    if entity.evidence is None:
        diagnostics.append("evidence: missing evidence")
    return _result(entity, diagnostics)


def validate_relation_candidate(
    candidate: RelationCandidate | ExtractedRelation | dict[str, Any],
    entities: Iterable[EntityCandidate | ExtractedEntity | dict[str, Any]],
) -> CandidateValidation:
    """Validate a relation and ensure both endpoints belong to its candidate set."""

    try:
        relation = _coerce(RelationCandidate, candidate)
    except (TypeError, ValidationError, ValueError) as exc:
        return _result(None, [f"candidate: invalid relation payload ({exc})"])

    diagnostics: list[str] = []
    if not relation.source.strip() or not relation.target.strip():
        diagnostics.append("endpoint: source and target must not be empty")
    names: set[str] = set()
    for entity in entities:
        try:
            parsed = _coerce(EntityCandidate, entity)
        except (TypeError, ValidationError, ValueError):
            continue
        names.add(parsed.name.strip().casefold())
    if relation.source.strip().casefold() not in names:
        diagnostics.append(f"endpoint: source {relation.source!r} is not in candidate set")
    if relation.target.strip().casefold() not in names:
        diagnostics.append(f"endpoint: target {relation.target!r} is not in candidate set")
    if not 0 <= relation.confidence <= 1:
        diagnostics.append("confidence: must be between 0 and 1")
    if relation.evidence is None:
        diagnostics.append("evidence: missing evidence")
    return _result(relation, diagnostics)


def validate_chunk_result(
    result: ChunkExtractionResult,
) -> tuple[list[CandidateValidation], list[CandidateValidation]]:
    """Validate all candidates in one chunk, preserving per-item diagnostics."""

    entities = [validate_entity_candidate(entity) for entity in result.entities]
    relations = [
        validate_relation_candidate(relation, result.entities)
        for relation in result.relations
    ]
    return entities, relations


# A descriptive alias for callers that prefer the candidate terminology.
validate_extraction_candidates = validate_chunk_result
