from app.resolution import (
    CanonicalEntityReference,
    DeterministicResolver,
    ResolutionMethod,
    ResolutionStatus,
    normalize_name,
)


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


def test_unresolved_keeps_source_identity_without_evidence_or_target():
    resolver = _resolver(_canonical("canonical:fastapi", "FastAPI"), fuzzy_threshold=0.95)

    result = resolver.resolve("doc-1::unknown", "Unknown", "doc-1", "chunk-9")

    assert result.status is ResolutionStatus.UNRESOLVED
    assert result.method is ResolutionMethod.FALLBACK
    assert result.canonical_id is None
    assert result.evidence is None
    assert result.source_entity_id == "doc-1::unknown"
