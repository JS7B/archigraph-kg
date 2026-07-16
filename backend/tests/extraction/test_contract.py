"""Public extraction contract and pipeline diagnostics tests."""

from app.extraction import (
    CandidateDecision,
    CandidateStatus,
    CandidateValidation,
    EntityCandidate,
    Evidence,
    EvidenceRef,
    RelationCandidate,
    ValidationDecision,
    ValidationResult,
    validate_entity_candidate,
    validate_extraction_candidates,
    validate_relation_candidate,
)
from app.extraction.models import DocumentExtraction, ExtractionStats
from app.extraction import pipeline
from app.parsing.models import ParsedDocument


def test_public_exports_keep_candidate_evidence_and_validation_contract():
    assert CandidateDecision is CandidateStatus
    assert ValidationDecision is CandidateStatus
    assert ValidationResult is CandidateValidation
    assert EvidenceRef is Evidence
    assert EntityCandidate.__name__ == "EntityCandidate"
    assert RelationCandidate.__name__ == "RelationCandidate"
    assert callable(validate_entity_candidate)
    assert callable(validate_relation_candidate)
    assert callable(validate_extraction_candidates)


def test_extraction_stats_diagnostics_is_optional_for_existing_callers():
    stats = ExtractionStats(
        document_id="doc",
        entity_count=1,
        relation_count=0,
        mention_count=1,
        failed_chunks=[],
    )

    assert stats.diagnostics == []


def test_pipeline_preserves_merge_diagnostics_in_stats(monkeypatch):
    diagnostics = ["doc#0 entity: evidence: missing evidence"]

    monkeypatch.setattr(pipeline, "extract_document", lambda doc, **kwargs: ([], []))

    def fake_merge(document_id, extractions, **kwargs):
        kwargs["diagnostics"].extend(diagnostics)
        from app.extraction.models import DocumentExtraction

        return DocumentExtraction()

    monkeypatch.setattr(pipeline, "merge_extractions", fake_merge)
    monkeypatch.setattr(pipeline, "write_extraction", lambda *args, **kwargs: (0, 0, 0))

    stats = pipeline.extract_and_ingest(
        object(),
        ParsedDocument(
            document_id="doc",
            source_path="doc.txt",
            doc_type="text",
            raw_text="",
            chunks=[],
        ),
    )

    assert stats.diagnostics == diagnostics


def test_pipeline_forwards_extraction_limits_and_progress(monkeypatch):
    captured = {}
    progress = lambda completed, total: None

    def fake_extract(doc, **kwargs):
        captured.update(kwargs)
        return [], []

    monkeypatch.setattr(pipeline, "extract_document", fake_extract)
    monkeypatch.setattr(
        pipeline,
        "merge_extractions",
        lambda *args, **kwargs: DocumentExtraction(),
    )
    monkeypatch.setattr(pipeline, "write_extraction", lambda *args, **kwargs: (0, 0, 0))

    pipeline.extract_and_ingest(
        object(),
        ParsedDocument(
            document_id="doc",
            source_path="doc.txt",
            doc_type="text",
            raw_text="",
            chunks=[],
        ),
        max_attempts=5,
        max_workers=2,
        on_progress=progress,
    )

    assert captured == {
        "max_attempts": 5,
        "max_workers": 2,
        "on_progress": progress,
    }
