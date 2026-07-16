from app.resolution import (
    CanonicalEntityReference,
    DeterministicResolver,
    ResolutionMethod,
    ResolutionStatus,
    normalize_name,
)
from app.resolution.normalization import normalize_name as module_normalize_name
import pytest


def _canonical(canonical_id: str, name: str):
    return CanonicalEntityReference(canonical_id=canonical_id, canonical_name=name)


def _resolver(*canonicals, aliases=(), **kwargs):
    return DeterministicResolver(canonicals, aliases=aliases, **kwargs)


def test_normalize_name_is_unicode_case_punctuation_and_whitespace_stable():
    value = "  Ｆａｓｔ　ＡＰＩ！  "

    assert normalize_name(value) == "fast api"
    assert normalize_name(normalize_name(value)) == normalize_name(value)
    assert normalize_name("FAST API") == "fast api"
    assert normalize_name(" 中文，名称 ") == "中文名称"
    assert module_normalize_name(value) == normalize_name(value)


def test_exact_match_is_accepted_with_evidence():
    resolver = _resolver(_canonical("canonical:fastapi", "FastAPI"))

    result = resolver.resolve(
        source_entity_id="doc-1::fastapi",
        source_name="FastAPI",
        source_document_id="doc-1",
        source_chunk_id="chunk-1",
    )

    assert result.status is ResolutionStatus.ACCEPTED
    assert result.method is ResolutionMethod.EXACT
    assert result.canonical_id == "canonical:fastapi"
    assert result.evidence is not None
    assert result.evidence.source_chunk_id == "chunk-1"


def test_explicit_alias_is_accepted_and_fastapi_spellings_share_identity():
    resolver = _resolver(
        _canonical("canonical:fastapi", "FastAPI"),
        aliases={"Fast API": "canonical:fastapi", "fastapi": "canonical:fastapi"},
    )

    result = resolver.resolve(
        source_entity_id="doc-2::fast-api",
        source_name="Fast API",
        source_document_id="doc-2",
        source_chunk_id="chunk-7",
    )

    assert result.status is ResolutionStatus.ACCEPTED
    assert result.method is ResolutionMethod.ALIAS
    assert result.canonical_id == "canonical:fastapi"


def test_colliding_exact_keys_are_review_not_auto_merged():
    resolver = _resolver(
        _canonical("canonical:a", "ＡＢ"),
        _canonical("canonical:b", "ab"),
    )

    result = resolver.resolve("doc-1::ab", "ab", "doc-1", "chunk-1")

    assert result.status is ResolutionStatus.REVIEW
    assert result.canonical_id is None
    assert result.method is ResolutionMethod.EXACT
    assert "ambiguous" in result.reason


def test_fuzzy_candidate_is_review_and_ties_do_not_choose_a_target():
    resolver = _resolver(
        _canonical("canonical:alpha", "GraphRAG"),
        _canonical("canonical:beta", "GraphRAG Guide"),
        fuzzy_threshold=0.4,
        ambiguity_margin=0.2,
    )

    result = resolver.resolve("doc-1::graphrag gu", "GraphRAG Gu", "doc-1", "chunk-1")

    assert result.status is ResolutionStatus.REVIEW
    assert result.method is ResolutionMethod.FUZZY
    assert result.canonical_id is None
    assert "ambiguous" in result.reason
    assert result.evidence is not None
    assert result.evidence.canonical_id is None
    assert result.evidence.source_chunk_id == "chunk-1"


def test_unresolved_keeps_source_identity_without_evidence_or_target():
    resolver = _resolver(_canonical("canonical:fastapi", "FastAPI"), fuzzy_threshold=0.95)

    result = resolver.resolve("doc-1::unknown", "Unknown", "doc-1", "chunk-9")

    assert result.status is ResolutionStatus.UNRESOLVED
    assert result.method is ResolutionMethod.FALLBACK
    assert result.canonical_id is None
    assert result.evidence is None
    assert result.source_entity_id == "doc-1::unknown"


def test_alias_to_unknown_canonical_is_rejected():
    resolver = _resolver(_canonical("canonical:fastapi", "FastAPI"))

    with pytest.raises(ValueError, match="unknown canonical_id"):
        resolver.register_alias("Fast API", "canonical:missing")


def test_resolver_does_not_infer_document_id_from_entity_id():
    resolver = _resolver(_canonical("canonical:fastapi", "FastAPI"))

    with pytest.raises(ValueError, match="document id"):
        resolver.resolve(
            source_entity_id="misleading-document::fastapi",
            source_name="FastAPI",
            source_chunk_id="chunk-1",
        )
