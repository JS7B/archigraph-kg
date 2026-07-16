"""Public extraction contract and pipeline diagnostics tests."""

from types import SimpleNamespace

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
from app.extraction.models import DocumentExtraction, ExtractionStats, MergedEntity
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
    monkeypatch.setattr(
        pipeline,
        "resolve_source_entities",
        lambda *args, **kwargs: SimpleNamespace(diagnostics=[]),
    )

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
    monkeypatch.setattr(
        pipeline,
        "resolve_source_entities",
        lambda *args, **kwargs: SimpleNamespace(diagnostics=[]),
    )

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


def test_pipeline_persists_overlay_after_source_graph_and_appends_diagnostics(monkeypatch):
    calls = []
    merged = DocumentExtraction(
        entities=[
            MergedEntity(
                entity_id="doc::neo4j",
                name="Neo4j",
                type="database",
                normalized_name="neo4j",
                mention_chunk_ids=["doc#0", "doc#1"],
            )
        ]
    )
    monkeypatch.setattr(pipeline, "extract_document", lambda *args, **kwargs: ([], []))
    monkeypatch.setattr(pipeline, "merge_extractions", lambda *args, **kwargs: merged)

    def fake_write(*args, **kwargs):
        calls.append("source")
        return 1, 0, 2

    def fake_resolve(driver, records, **kwargs):
        calls.append("canonical")
        record = list(records)[0]
        assert record.document_id == "doc"
        assert record.mention_chunk_ids == ["doc#0", "doc#1"]
        return SimpleNamespace(diagnostics=["resolution summary: accepted=1"])

    monkeypatch.setattr(pipeline, "write_extraction", fake_write)
    monkeypatch.setattr(pipeline, "resolve_source_entities", fake_resolve)

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

    assert calls == ["source", "canonical"]
    assert stats.entity_count == 1
    assert stats.diagnostics == ["resolution summary: accepted=1"]
