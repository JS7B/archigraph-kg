from app.extraction.models import (
    CandidateStatus,
    EntityCandidate,
    Evidence,
    RelationCandidate,
)
from app.extraction.validation import (
    validate_entity_candidate,
    validate_relation_candidate,
)


def _evidence() -> Evidence:
    return Evidence(chunk_id="doc#0", text="FastAPI is a web framework.")


def test_entity_without_evidence_requires_review():
    candidate = EntityCandidate(name="FastAPI", type="技术")

    result = validate_entity_candidate(candidate)

    assert result.status is CandidateStatus.REVIEW
    assert "evidence" in " ".join(result.diagnostics)


def test_unknown_entity_type_is_rejected():
    candidate = EntityCandidate(name="FastAPI", type="unknown", evidence=_evidence())

    result = validate_entity_candidate(candidate)

    assert result.status is CandidateStatus.REJECTED
    assert any("type" in diagnostic for diagnostic in result.diagnostics)


def test_empty_entity_name_is_rejected():
    candidate = EntityCandidate(name="   ", type="技术", evidence=_evidence())

    result = validate_entity_candidate(candidate)

    assert result.status is CandidateStatus.REJECTED
    assert any("name" in diagnostic for diagnostic in result.diagnostics)


def test_relation_confidence_outside_range_is_rejected():
    candidate = RelationCandidate(
        source="FastAPI",
        target="Python",
        type="依赖",
        confidence=1.1,
        evidence=_evidence(),
    )
    entities = [
        EntityCandidate(name="FastAPI", type="技术", evidence=_evidence()),
        EntityCandidate(name="Python", type="技术", evidence=_evidence()),
    ]

    result = validate_relation_candidate(candidate, entities)

    assert result.status is CandidateStatus.REJECTED
    assert any("confidence" in diagnostic for diagnostic in result.diagnostics)


def test_relation_with_dangling_endpoint_is_rejected():
    candidate = RelationCandidate(
        source="FastAPI",
        target="Missing",
        type="依赖",
        evidence=_evidence(),
    )
    entities = [EntityCandidate(name="FastAPI", type="技术", evidence=_evidence())]

    result = validate_relation_candidate(candidate, entities)

    assert result.status is CandidateStatus.REJECTED
    assert any("endpoint" in diagnostic for diagnostic in result.diagnostics)


def test_valid_entity_is_accepted():
    candidate = EntityCandidate(name="FastAPI", type="技术", evidence=_evidence())

    result = validate_entity_candidate(candidate)

    assert result.status is CandidateStatus.ACCEPTED
    assert result.diagnostics == []
