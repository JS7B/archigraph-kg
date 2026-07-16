from __future__ import annotations

from app.resolution.models import (
    CanonicalEntityReference,
    ResolutionCandidate,
    ResolutionEvidence,
    ResolutionMethod,
    ResolutionStatus,
    SourceEntityRecord,
)
from app.resolution.persistence import (
    _WRITE_ACCEPTED,
    _WRITE_REVIEW_OR_UNRESOLVED,
    CanonicalOverlayStore,
)


class FakeDriver:
    def __init__(self, records=None):
        self.calls = []
        self.records = records if records is not None else [{"written": 1}]

    def execute_query(self, query, **params):
        self.calls.append((query, params))
        return self.records, None, None


def _source():
    return SourceEntityRecord(
        entity_id="doc::fastapi",
        name="FastAPI",
        entity_type="framework",
        normalized_name="fastapi",
        document_id="doc",
        mention_chunk_ids=["chunk-1", "chunk-2"],
    )


def _accepted():
    evidence = ResolutionEvidence(
        source_entity_id="doc::fastapi",
        source_document_id="doc",
        source_chunk_id="chunk-1",
        canonical_id="canonical:v1:abc",
        method=ResolutionMethod.BOOTSTRAP,
        score=1.0,
        reason="new normalized name",
    )
    return ResolutionCandidate(
        source_entity_id="doc::fastapi",
        source_name="FastAPI",
        source_document_id="doc",
        source_chunk_id="chunk-1",
        canonical_id="canonical:v1:abc",
        status=ResolutionStatus.ACCEPTED,
        method=ResolutionMethod.BOOTSTRAP,
        score=1.0,
        reason=evidence.reason,
        evidence=evidence,
    )


def test_accepted_cypher_matches_real_document_chunk_mention_before_linking():
    compact = " ".join(_WRITE_ACCEPTED.split())

    assert "MATCH (document:Document {document_id: $source_document_id})" in compact
    assert "-[:HAS_CHUNK]->(evidence:Chunk {chunk_id: $evidence_chunk_id})" in compact
    assert "-[:MENTIONS]->(source)" in compact
    assert "MERGE (canonical:CanonicalEntity {canonical_id: $canonical_id})" in compact
    assert "MERGE (source)-[resolution:RESOLVES_TO]->(canonical)" in compact
    assert "canonical:Entity" not in compact


def test_write_accepted_uses_one_real_evidence_and_explicit_document_id():
    driver = FakeDriver()
    store = CanonicalOverlayStore(driver)

    store.write_decision(_source(), _accepted())

    query, params = driver.calls[0]
    assert query == _WRITE_ACCEPTED
    assert params["source_document_id"] == "doc"
    assert params["evidence_chunk_id"] == "chunk-1"
    assert "chunk-2" not in params.values()
    assert params["database_"] == "neo4j"


def test_review_write_deletes_old_link_and_persists_sorted_candidate_ids():
    driver = FakeDriver()
    store = CanonicalOverlayStore(driver)
    review = ResolutionCandidate(
        source_entity_id="doc::fastapi",
        source_name="FastAPI",
        source_document_id="doc",
        source_chunk_id="chunk-1",
        status=ResolutionStatus.REVIEW,
        method=ResolutionMethod.EXACT,
        score=1.0,
        reason="collision",
        evidence=ResolutionEvidence(
            source_entity_id="doc::fastapi",
            source_document_id="doc",
            source_chunk_id="chunk-1",
            canonical_id=None,
            method=ResolutionMethod.EXACT,
            score=1.0,
            reason="collision",
        ),
        candidate_canonical_ids=["z", "a", "a"],
    )

    store.write_decision(_source(), review)

    query, params = driver.calls[0]
    assert query == _WRITE_REVIEW_OR_UNRESOLVED
    assert "DELETE previous" in query
    assert params["candidate_canonical_ids"] == ["a", "z"]
    assert "OPTIONAL MATCH (source)-[previous:RESOLVES_TO]" in query


def test_accepted_write_clears_stale_review_state_and_replaces_old_target():
    compact = " ".join(_WRITE_ACCEPTED.split())

    assert "OPTIONAL MATCH (source)-[previous:RESOLVES_TO]" in compact
    assert "DELETE previous" in compact
    assert "REMOVE source.resolution_status" in compact


def test_accepted_noop_due_to_missing_evidence_is_an_ingestion_failure():
    store = CanonicalOverlayStore(FakeDriver(records=[{"written": 0}]))

    try:
        store.write_decision(_source(), _accepted())
    except RuntimeError as exc:
        assert "source/document/mention evidence" in str(exc)
    else:
        raise AssertionError("missing graph evidence must fail")


def test_load_aliases_only_uses_accepted_alias_edges_with_matching_evidence():
    driver = FakeDriver(records=[])
    CanonicalOverlayStore(driver).load_reconstructed_aliases()

    query = " ".join(driver.calls[0][0].split())
    assert "RESOLVES_TO" in query
    assert "resolution.method = 'alias'" in query
    assert "(evidence:Chunk)-[:MENTIONS]->(source:Entity)" in query
    assert "resolution.evidence_chunk_id = evidence.chunk_id" in query


def test_source_load_query_reads_document_id_property_in_stable_order():
    driver = FakeDriver(records=[])
    CanonicalOverlayStore(driver).load_source_entities()

    compact = " ".join(driver.calls[0][0].split())
    assert "source.document_id AS document_id" in compact
    assert (
        "OPTIONAL MATCH (document:Document)-[:HAS_CHUNK]->"
        "(evidence:Chunk)-[:MENTIONS]->(source)" in compact
    )
    assert "WHERE document.document_id = source.document_id" in compact
    assert "ORDER BY source.entity_id" in compact
    assert "split" not in compact.lower()
