from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from app.resolution.identity import canonical_id_for_name
from app.resolution.models import (
    AcceptedResolutionRecord,
    AliasRecord,
    CanonicalEntityReference,
    ResolutionMethod,
    ResolutionStatus,
    SourceEntityRecord,
)
from app.resolution import service


@dataclass
class FakeStore:
    canonicals: list[CanonicalEntityReference] = field(default_factory=list)
    aliases: list[AliasRecord] = field(default_factory=list)
    valid_aliases: list[AliasRecord] = field(default_factory=list)
    existing: dict[str, AcceptedResolutionRecord] = field(default_factory=dict)
    writes: list[tuple[SourceEntityRecord, object]] = field(default_factory=list)
    orphan_cleanup_calls: int = 0

    def load_canonicals(self):
        return list(self.canonicals)

    def load_reconstructed_aliases(self):
        return list(self.aliases)

    def load_existing_resolutions(self):
        return dict(self.existing)

    def validate_aliases(self, records):
        records = list(records)
        if records != self.valid_aliases:
            raise ValueError("alias provenance is not valid in the source graph")
        return records

    def write_decision(self, source, decision):
        self.writes.append((source, decision))

    def remove_orphan_canonicals(self):
        self.orphan_cleanup_calls += 1


def _source(entity_id: str, name: str, document_id: str, *chunks: str, entity_type="technology"):
    return SourceEntityRecord(
        entity_id=entity_id,
        name=name,
        entity_type=entity_type,
        normalized_name=name.lower(),
        document_id=document_id,
        mention_chunk_ids=list(chunks),
    )


def test_canonical_id_is_stable_across_normalization_type_and_repeated_calls():
    expected = canonical_id_for_name("Fast API")

    assert expected.startswith("canonical:v1:")
    assert expected == canonical_id_for_name("  FAST API！ ")
    assert expected == canonical_id_for_name("Ｆａｓｔ　ＡＰＩ")
    assert expected == canonical_id_for_name("Fast API", entity_type="framework")
    assert expected == canonical_id_for_name("Fast API", entity_type="product")


def test_service_bootstraps_once_then_exact_matches_in_stable_source_order():
    store = FakeStore()
    records = [
        _source("doc-b::fastapi", "FAST API", "doc-b", "chunk-b"),
        _source("doc-a::fastapi", "Fast API!", "doc-a", "chunk-a"),
    ]

    result = service.resolve_source_entities(object(), records, store=store)

    assert [source.entity_id for source, _ in store.writes] == [
        "doc-a::fastapi",
        "doc-b::fastapi",
    ]
    first, second = [decision for _, decision in store.writes]
    assert first.status is ResolutionStatus.ACCEPTED
    assert first.method is ResolutionMethod.BOOTSTRAP
    assert second.status is ResolutionStatus.ACCEPTED
    assert second.method is ResolutionMethod.EXACT
    assert first.canonical_id == second.canonical_id == canonical_id_for_name("Fast API")
    assert first.evidence.source_chunk_id == "chunk-a"
    assert second.evidence.source_chunk_id == "chunk-b"
    assert result.accepted_count == 2
    assert result.bootstrap_count == 1


def test_missing_mentions_is_unresolved_and_never_bootstraps():
    store = FakeStore()

    result = service.resolve_source_entities(
        object(), [_source("doc-a::orphan", "Orphan", "doc-a")], store=store
    )

    decision = store.writes[0][1]
    assert decision.status is ResolutionStatus.UNRESOLVED
    assert decision.canonical_id is None
    assert decision.source_chunk_id is None
    assert result.accepted_count == 0
    assert result.unresolved_count == 1


def test_fuzzy_and_exact_collision_remain_review_with_sorted_candidates():
    collision_a = CanonicalEntityReference(canonical_id="canonical:z", canonical_name="ＡＢ")
    collision_b = CanonicalEntityReference(canonical_id="canonical:a", canonical_name="ab")
    store = FakeStore(canonicals=[collision_a, collision_b])

    service.resolve_source_entities(
        object(), [_source("doc::ab", "ab", "doc", "chunk")], store=store
    )

    collision = store.writes[0][1]
    assert collision.status is ResolutionStatus.REVIEW
    assert collision.canonical_id is None
    assert collision.candidate_canonical_ids == ["canonical:a", "canonical:z"]

    fuzzy_store = FakeStore(
        canonicals=[
            CanonicalEntityReference(canonical_id="canonical:z", canonical_name="GraphRAG"),
            CanonicalEntityReference(canonical_id="canonical:a", canonical_name="GraphRAG Guide"),
        ]
    )
    service.resolve_source_entities(
        object(),
        [_source("doc::graph", "GraphRAG Gu", "doc", "chunk")],
        store=fuzzy_store,
        fuzzy_threshold=0.4,
        ambiguity_margin=0.2,
    )
    fuzzy = fuzzy_store.writes[0][1]
    assert fuzzy.status is ResolutionStatus.REVIEW
    assert fuzzy.canonical_id is None
    assert fuzzy.candidate_canonical_ids == ["canonical:a", "canonical:z"]


def test_first_time_alias_requires_store_validated_provenance_and_is_reusable():
    canonical = CanonicalEntityReference(
        canonical_id="canonical:postgresql", canonical_name="PostgreSQL"
    )
    alias = AliasRecord(
        alias="Postgres",
        canonical_id=canonical.canonical_id,
        source_entity_id="doc::postgres",
        source_document_id="doc",
        source_chunk_id="chunk",
    )
    store = FakeStore(canonicals=[canonical], valid_aliases=[alias])
    source = _source("doc::postgres", "Postgres", "doc", "chunk")

    service.resolve_source_entities(object(), [source], aliases=[alias], store=store)

    decision = store.writes[0][1]
    assert decision.status is ResolutionStatus.ACCEPTED
    assert decision.method is ResolutionMethod.ALIAS
    assert decision.canonical_id == canonical.canonical_id

    reconstructed = FakeStore(canonicals=[canonical], aliases=[alias])
    service.resolve_source_entities(object(), [source], store=reconstructed)
    assert reconstructed.writes[0][1].method is ResolutionMethod.ALIAS

    invalid = FakeStore(canonicals=[canonical])
    with pytest.raises(ValueError, match="alias provenance"):
        service.resolve_source_entities(object(), [source], aliases=[alias], store=invalid)


def test_validated_alias_overrides_an_existing_bootstrap_identity():
    source = _source("doc::postgres", "Postgres", "doc", "chunk")
    bootstrap_id = canonical_id_for_name(source.name)
    target_id = canonical_id_for_name("PostgreSQL")
    alias = AliasRecord(
        alias=source.name,
        canonical_id=target_id,
        source_entity_id=source.entity_id,
        source_document_id=source.document_id,
        source_chunk_id="chunk",
    )
    store = FakeStore(
        canonicals=[
            CanonicalEntityReference(
                canonical_id=bootstrap_id, canonical_name=source.name
            ),
            CanonicalEntityReference(
                canonical_id=target_id, canonical_name="PostgreSQL"
            ),
        ],
        valid_aliases=[alias],
        existing={
            source.entity_id: AcceptedResolutionRecord(
                source_entity_id=source.entity_id,
                source_document_id=source.document_id,
                source_chunk_id="chunk",
                canonical_id=bootstrap_id,
                method=ResolutionMethod.BOOTSTRAP,
                score=1.0,
                reason="new normalized name bootstrapped deterministically",
            )
        },
    )

    service.resolve_source_entities(object(), [source], aliases=[alias], store=store)

    decision = store.writes[0][1]
    assert decision.status is ResolutionStatus.ACCEPTED
    assert decision.method is ResolutionMethod.ALIAS
    assert decision.canonical_id == target_id


def test_alias_collision_keeps_all_targets_for_review():
    aliases = [
        AliasRecord(
            alias="PG",
            canonical_id=canonical_id,
            source_entity_id=f"seed::{canonical_id}",
            source_document_id="seed",
            source_chunk_id=f"chunk::{canonical_id}",
        )
        for canonical_id in ("canonical:z", "canonical:a")
    ]
    store = FakeStore(
        canonicals=[
            CanonicalEntityReference(canonical_id="canonical:z", canonical_name="PostgreSQL"),
            CanonicalEntityReference(canonical_id="canonical:a", canonical_name="Pig"),
            CanonicalEntityReference(canonical_id="canonical:pg", canonical_name="PG"),
        ],
        aliases=aliases,
    )

    service.resolve_source_entities(
        object(), [_source("doc::pg", "PG", "doc", "chunk")], store=store
    )

    decision = store.writes[0][1]
    assert decision.status is ResolutionStatus.REVIEW
    assert decision.method is ResolutionMethod.ALIAS
    assert decision.candidate_canonical_ids == ["canonical:a", "canonical:z"]


def test_runtime_uses_explicit_document_id_not_entity_id_prefix():
    store = FakeStore()
    source = _source("misleading-prefix::entity", "Entity", "explicit-document", "chunk")

    service.resolve_source_entities(object(), [source], store=store)

    decision = store.writes[0][1]
    assert decision.source_document_id == "explicit-document"
    assert decision.evidence.source_document_id == "explicit-document"


def test_type_drift_does_not_create_a_second_canonical():
    store = FakeStore()
    records = [
        _source("a::neo4j", "Neo4j", "a", "a#0", entity_type="database"),
        _source("b::neo4j", "neo4j", "b", "b#0", entity_type="product"),
    ]

    service.resolve_source_entities(object(), records, store=store)

    assert {decision.canonical_id for _, decision in store.writes} == {
        canonical_id_for_name("Neo4j")
    }


def test_repeated_run_preserves_existing_bootstrap_edge_provenance():
    source = _source("doc::neo4j", "Neo4j", "doc", "chunk")
    canonical_id = canonical_id_for_name("Neo4j")
    store = FakeStore(
        canonicals=[
            CanonicalEntityReference(canonical_id=canonical_id, canonical_name="Neo4j")
        ],
        existing={
            source.entity_id: AcceptedResolutionRecord(
                source_entity_id=source.entity_id,
                source_document_id=source.document_id,
                source_chunk_id="chunk",
                canonical_id=canonical_id,
                method=ResolutionMethod.BOOTSTRAP,
                score=1.0,
                reason="new normalized name bootstrapped deterministically",
            )
        },
    )

    service.resolve_source_entities(object(), [source], store=store)

    decision = store.writes[0][1]
    assert decision.method is ResolutionMethod.BOOTSTRAP
    assert decision.evidence.source_chunk_id == "chunk"
