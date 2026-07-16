import pytest

from evals.quality_baseline import build_quality_baseline, render_quality_report
from evals.quality_fixtures import (
    CandidateEntity,
    CandidateRelation,
    QualityFixture,
    ReviewScope,
    load_quality_fixtures,
)
from evals.quality_metrics import (
    graph_structure_diagnostics,
    relation_review_candidate_ids,
    summarize_entity_precision,
    summarize_entity_review_coverage,
    summarize_provenance_completeness,
    summarize_relation_review_coverage,
    summarize_relation_semantic_precision,
)


def _entity(
    entity_id: str,
    *,
    name: str | None = None,
    reviewed_correct: bool | None = True,
    evidence_present: bool = True,
) -> CandidateEntity:
    return CandidateEntity(
        entity_id=entity_id,
        name=name or entity_id,
        type="concept",
        accepted=True,
        matched_gold=reviewed_correct is True,
        reviewed_correct=reviewed_correct,
        evidence_present=evidence_present,
    )


def _relation(
    relation_id: str,
    source: str,
    target: str,
    *,
    semantically_correct: bool | None = True,
    evidence_present: bool = True,
    confidence: float = 0.9,
) -> CandidateRelation:
    return CandidateRelation(
        relation_id=relation_id,
        source_entity_id=source,
        target_entity_id=target,
        source=source,
        type="relates",
        target=target,
        accepted=True,
        matched_gold=semantically_correct is True,
        semantically_correct=semantically_correct,
        evidence_present=evidence_present,
        confidence=confidence,
    )


def _fixture(
    sample_id: str,
    entities: list[CandidateEntity],
    relations: list[CandidateRelation],
) -> QualityFixture:
    return QualityFixture(
        sample_id=sample_id,
        text_kind="prose",
        review_scope=ReviewScope(
            accepted_entity_population=len(entities),
            accepted_relation_population=len(relations),
            selection_method="complete test fixture review",
        ),
        gold_entities=[{"name": "Gold", "type": "concept"}],
        gold_relations=[],
        candidate_entities=entities,
        candidate_relations=relations,
    )


@pytest.mark.parametrize(
    ("labels", "expected"),
    [([True, True], (2, 2, 1.0)), ([True, False], (1, 2, 0.5)), ([], (0, 0, None))],
)
def test_entity_precision_positive_negative_and_empty(labels, expected):
    entities = [_entity(f"e{index}", reviewed_correct=label) for index, label in enumerate(labels)]
    fixtures = [_fixture("doc", entities, [])] if entities else []

    result = summarize_entity_precision(fixtures)

    assert (result.numerator, result.denominator, result.rate) == expected


@pytest.mark.parametrize(
    ("labels", "expected"),
    [([True, True], (2, 2, 1.0)), ([True, False], (1, 2, 0.5)), ([], (0, 0, None))],
)
def test_relation_semantic_precision_positive_negative_and_empty(labels, expected):
    entities = [_entity("source"), _entity("target")]
    relations = [
        _relation(f"r{index}", "source", "target", semantically_correct=label)
        for index, label in enumerate(labels)
    ]
    fixtures = [_fixture("doc", entities, relations)] if relations else []

    result = summarize_relation_semantic_precision(fixtures)

    assert (result.numerator, result.denominator, result.rate) == expected


@pytest.mark.parametrize(
    ("evidence", "expected"),
    [([True, True], (2, 2, 1.0)), ([True, False], (1, 2, 0.5)), ([], (0, 0, None))],
)
def test_provenance_completeness_positive_negative_and_empty(evidence, expected):
    entities = [_entity(f"e{index}", evidence_present=value) for index, value in enumerate(evidence)]
    fixtures = [_fixture("doc", entities, [])] if entities else []

    result = summarize_provenance_completeness(fixtures)

    assert (result.numerator, result.denominator, result.rate) == expected


def test_provenance_completeness_combines_entities_and_relations():
    entities = [_entity("source"), _entity("target")]
    relations = [_relation("r", "source", "target", evidence_present=False)]

    result = summarize_provenance_completeness(
        [_fixture("doc", entities, relations)]
    )

    assert (result.numerator, result.denominator, result.rate) == (2, 3, 2 / 3)


def test_review_candidates_do_not_reduce_precision_denominator():
    entities = [_entity("reviewed"), _entity("candidate", reviewed_correct=None)]
    fixture = _fixture("doc", entities, [])

    baseline = build_quality_baseline([fixture])

    assert baseline.entity_precision.denominator == 1
    assert baseline.entity_precision.rate == 1.0
    assert baseline.entity_review_coverage.numerator == 1
    assert baseline.entity_review_coverage.denominator == 2
    assert baseline.entity_review_candidates == ("candidate",)


@pytest.mark.parametrize(
    ("labels", "expected"),
    [([True, False], (2, 2, 1.0)), ([True, None], (1, 2, 0.5)), ([], (0, 0, None))],
)
def test_entity_review_coverage_full_partial_and_empty(labels, expected):
    entities = [
        _entity(f"e{index}", reviewed_correct=label)
        for index, label in enumerate(labels)
    ]
    fixtures = [_fixture("doc", entities, [])] if entities else []

    result = summarize_entity_review_coverage(fixtures)

    assert (result.numerator, result.denominator, result.rate) == expected


@pytest.mark.parametrize(
    ("labels", "expected"),
    [([True, False], (2, 2, 1.0)), ([True, None], (1, 2, 0.5)), ([], (0, 0, None))],
)
def test_relation_review_coverage_full_partial_and_empty(labels, expected):
    entities = [_entity("source"), _entity("target")]
    relations = [
        _relation(f"r{index}", "source", "target", semantically_correct=label)
        for index, label in enumerate(labels)
    ]
    fixtures = [_fixture("doc", entities, relations)] if relations else []

    result = summarize_relation_review_coverage(fixtures)

    assert (result.numerator, result.denominator, result.rate) == expected


def test_only_unmatched_unreviewed_relation_stays_a_review_candidate():
    entities = [_entity("source"), _entity("target")]
    relations = [
        _relation("confirmed-correct", "source", "target", semantically_correct=True),
        _relation("confirmed-wrong", "source", "target", semantically_correct=False),
        _relation("pending", "source", "target", semantically_correct=None),
    ]

    result = relation_review_candidate_ids([_fixture("doc", entities, relations)])

    assert result == ("pending",)


def test_structural_diagnostics_reports_every_requested_signal():
    first = _fixture(
        "doc-a",
        [
            _entity("hub", name="系统"),
            _entity("leaf-a", name="Neo4j"),
            _entity("leaf-b"),
            _entity("leaf-c"),
            _entity("isolated"),
        ],
        [
            _relation("r1", "hub", "leaf-a"),
            _relation("r2", "hub", "leaf-b", confidence=0.2),
            _relation("r3", "hub", "leaf-c"),
        ],
    )
    second = _fixture("doc-b", [_entity("duplicate", name=" neo4j ")], [])

    result = graph_structure_diagnostics(
        [first, second],
        low_confidence_threshold=0.5,
        generic_names={"系统"},
        hub_degree_threshold=3,
    )

    assert result.isolated_entity_ids == ("duplicate", "isolated")
    assert result.degree_one_entity_ids == ("leaf-a", "leaf-b", "leaf-c")
    assert result.low_confidence_relation_ids == ("r2",)
    assert result.duplicate_normalized_names == {"neo4j": ("doc-a", "doc-b")}
    assert result.component_sizes == (4, 1, 1)
    assert result.suspicious_generic_hub_ids == ("hub",)


def test_structural_diagnostics_clean_and_empty_inputs():
    clean = _fixture(
        "doc",
        [_entity("a"), _entity("b")],
        [_relation("r", "a", "b", confidence=0.9)],
    )

    result = graph_structure_diagnostics(
        [clean], low_confidence_threshold=0.5, generic_names={"系统"}, hub_degree_threshold=3
    )
    empty = graph_structure_diagnostics(
        [], low_confidence_threshold=0.5, generic_names={"系统"}, hub_degree_threshold=3
    )

    assert result.isolated_entity_ids == ()
    assert result.low_confidence_relation_ids == ()
    assert result.duplicate_normalized_names == {}
    assert result.suspicious_generic_hub_ids == ()
    assert result.component_sizes == (2,)
    assert empty.component_sizes == ()


def test_reviewed_fixture_baseline_has_denominators_and_full_provenance():
    baseline = build_quality_baseline(load_quality_fixtures())
    report = render_quality_report(baseline)

    assert baseline.entity_precision.denominator > 0
    assert baseline.relation_semantic_precision.denominator > 0
    assert baseline.provenance_completeness.denominator > 0
    assert baseline.provenance_completeness.rate == 1.0
    assert "100.0%" in report
    assert "人工复核夹具" in report
    assert "不能替代真实模型基线" in report


def test_committed_quality_report_matches_the_deterministic_renderer():
    report = render_quality_report(build_quality_baseline(load_quality_fixtures()))
    report_path = __import__("pathlib").Path(__file__).parents[1] / "quality_report.md"

    assert report_path.read_text(encoding="utf-8") == report
