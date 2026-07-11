import pytest
from pydantic import ValidationError

from app.resolution import (
    AliasRecord,
    CanonicalEntityReference,
    ResolutionCandidate,
    ResolutionEvidence,
    ResolutionMethod,
    ResolutionStatus,
)


def _evidence(**overrides):
    data = {
        "source_entity_id": "doc-1::fastapi",
        "source_document_id": "doc-1",
        "source_chunk_id": "chunk-1",
        "canonical_id": "canonical:fastapi",
        "method": ResolutionMethod.EXACT,
        "score": 1.0,
        "reason": "normalized keys match",
    }
    data.update(overrides)
    return ResolutionEvidence.model_validate(data)


def test_unresolved_candidate_has_safe_defaults_and_keeps_source_identity():
    candidate = ResolutionCandidate(
        source_entity_id="doc-1::unknown",
        source_name="Unknown",
        source_document_id="doc-1",
        source_chunk_id="chunk-9",
    )

    assert candidate.status is ResolutionStatus.UNRESOLVED
    assert candidate.method is ResolutionMethod.FALLBACK
    assert candidate.canonical_id is None
    assert candidate.evidence is None
    assert candidate.model_dump()["source_entity_id"] == "doc-1::unknown"


def test_evidence_requires_non_empty_provenance_and_reason():
    with pytest.raises(ValidationError):
        _evidence(source_chunk_id=" ")
    with pytest.raises(ValidationError):
        _evidence(reason="")
    with pytest.raises(ValidationError):
        _evidence(score=-0.01)
    with pytest.raises(ValidationError):
        _evidence(score=1.01)


def test_accepted_candidate_requires_evidence():
    with pytest.raises(ValidationError):
        ResolutionCandidate(
            source_entity_id="doc-1::fastapi",
            source_name="FastAPI",
            source_document_id="doc-1",
            source_chunk_id="chunk-1",
            canonical_id="canonical:fastapi",
            status=ResolutionStatus.ACCEPTED,
            method=ResolutionMethod.EXACT,
            score=1.0,
        )


def test_contract_models_serialize_provenance_and_enums():
    canonical = CanonicalEntityReference(
        canonical_id="canonical:fastapi",
        canonical_name="FastAPI",
        entity_type="framework",
        source_document_ids=["doc-1"],
        source_chunk_ids=["chunk-1"],
    )
    alias = AliasRecord(
        alias="fast api",
        canonical_id=canonical.canonical_id,
        source_entity_id="doc-2::fast api",
        source_document_id="doc-2",
        source_chunk_id="chunk-7",
    )
    candidate = ResolutionCandidate(
        source_entity_id="doc-1::fastapi",
        source_name="FastAPI",
        source_document_id="doc-1",
        source_chunk_id="chunk-1",
        canonical_id=canonical.canonical_id,
        status=ResolutionStatus.ACCEPTED,
        method=ResolutionMethod.EXACT,
        score=1.0,
        evidence=_evidence(),
    )

    assert canonical.model_dump() == {
        "canonical_id": "canonical:fastapi",
        "canonical_name": "FastAPI",
        "entity_type": "framework",
        "source_document_ids": ["doc-1"],
        "source_chunk_ids": ["chunk-1"],
    }
    assert alias.model_dump()["source_chunk_id"] == "chunk-7"
    dumped = candidate.model_dump(mode="json")
    assert dumped["status"] == "accepted"
    assert dumped["evidence"]["canonical_id"] == "canonical:fastapi"
