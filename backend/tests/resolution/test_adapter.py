from copy import deepcopy

from app.extraction.models import MergedEntity
from app.resolution import (
    CanonicalEntityReference,
    DeterministicResolver,
    ResolutionAdapter,
    ResolutionStatus,
    adapt_merged_entities,
)


def _entity(entity_id: str, name: str, *chunks: str) -> MergedEntity:
    return MergedEntity(
        entity_id=entity_id,
        name=name,
        type="technology",
        normalized_name=name.lower(),
        mention_chunk_ids=list(chunks),
    )


def test_adapter_groups_accepted_entities_and_retains_all_mention_evidence():
    entities = [
        _entity("doc-1::fastapi", "FastAPI", "chunk-1", "chunk-2"),
        _entity("doc-2::fast-api", "Fast API", "chunk-9"),
    ]
    resolver = DeterministicResolver(
        [CanonicalEntityReference(canonical_id="tech:fastapi", canonical_name="FastAPI")],
        aliases={"Fast API": "tech:fastapi"},
    )

    result = ResolutionAdapter(resolver).adapt(entities)

    assert all(candidate.status is ResolutionStatus.ACCEPTED for candidate in result.candidates)
    assert len(result.groups) == 1
    group = result.groups[0]
    assert group.canonical_id == "tech:fastapi"
    assert group.source_entity_ids == ["doc-1::fastapi", "doc-2::fast-api"]
    assert group.source_document_ids == ["doc-1", "doc-2"]
    assert group.mention_chunk_ids == ["chunk-1", "chunk-2", "chunk-9"]
    assert [e.source_chunk_id for e in group.evidence] == ["chunk-1", "chunk-2", "chunk-9"]


def test_unresolved_entity_uses_document_scoped_fallback_and_keeps_provenance():
    entities = [_entity("doc-3::mystery", "Mystery", "chunk-4")]
    resolver = DeterministicResolver(
        [CanonicalEntityReference(canonical_id="tech:fastapi", canonical_name="FastAPI")],
        fuzzy_threshold=0.99,
    )

    result = adapt_merged_entities(entities, resolver)

    assert result.candidates[0].status is ResolutionStatus.UNRESOLVED
    assert result.candidates[0].source_entity_id == "doc-3::mystery"
    assert result.groups[0].canonical_id == "doc-3::mystery"
    assert result.groups[0].fallback is True
    assert result.groups[0].mention_chunk_ids == ["chunk-4"]
    assert result.diagnostics


def test_review_candidate_is_not_silently_added_to_canonical_group():
    entities = [_entity("doc-1::graph", "GraphRAG Gu", "chunk-5")]
    resolver = DeterministicResolver(
        [
            CanonicalEntityReference(canonical_id="a", canonical_name="GraphRAG"),
            CanonicalEntityReference(canonical_id="b", canonical_name="GraphRAG Guide"),
        ],
        fuzzy_threshold=0.4,
        ambiguity_margin=0.2,
    )

    result = ResolutionAdapter(resolver).adapt(entities)

    assert result.candidates[0].status is ResolutionStatus.REVIEW
    assert result.candidates[0].canonical_id is None
    assert result.groups[0].canonical_id == "doc-1::graph"
    assert result.groups[0].fallback is True
    assert "review" in result.diagnostics[0]


def test_adapter_does_not_mutate_input_entities():
    entities = [_entity("doc-1::fastapi", "FastAPI", "chunk-1")]
    before = deepcopy(entities)

    ResolutionAdapter().adapt(entities)

    assert entities == before


def test_missing_mentions_never_create_synthetic_accepted_evidence():
    result = ResolutionAdapter().adapt([_entity("doc-1::fastapi", "FastAPI")])

    assert result.candidates[0].status is ResolutionStatus.UNRESOLVED
    assert result.candidates[0].evidence is None
    assert result.groups[0].canonical_id == "doc-1::fastapi"


def test_alias_group_keeps_source_document_ids_in_input_order():
    resolver = DeterministicResolver(
        [CanonicalEntityReference(canonical_id="tech:fastapi", canonical_name="FastAPI")],
        aliases={"Fast API": "tech:fastapi"},
    )
    result = ResolutionAdapter(resolver).adapt(
        [
            _entity("first::fastapi", "FastAPI", "chunk-1"),
            _entity("second::fast-api", "Fast API", "chunk-2"),
        ]
    )

    assert result.groups[0].source_document_ids == ["first", "second"]
