"""Pure metrics for a manually reviewed graph-quality sample."""

from dataclasses import dataclass

from evals.quality_fixtures import QualityFixture


@dataclass(frozen=True)
class RatioMetric:
    numerator: int
    denominator: int

    @property
    def rate(self) -> float | None:
        return self.numerator / self.denominator if self.denominator else None


@dataclass(frozen=True)
class StructuralDiagnostics:
    isolated_entity_ids: tuple[str, ...]
    degree_one_entity_ids: tuple[str, ...]
    low_confidence_relation_ids: tuple[str, ...]
    duplicate_normalized_names: dict[str, tuple[str, ...]]
    component_sizes: tuple[int, ...]
    suspicious_generic_hub_ids: tuple[str, ...]

    @property
    def component_size_distribution(self) -> dict[int, int]:
        return {
            size: self.component_sizes.count(size)
            for size in sorted(set(self.component_sizes))
        }


def _accepted_entities(fixtures: list[QualityFixture]):
    return [
        (fixture.sample_id, entity)
        for fixture in fixtures
        for entity in fixture.candidate_entities
        if entity.accepted
    ]


def _accepted_relations(fixtures: list[QualityFixture]):
    return [
        relation
        for fixture in fixtures
        for relation in fixture.candidate_relations
        if relation.accepted
    ]


def summarize_entity_precision(fixtures: list[QualityFixture]) -> RatioMetric:
    """Precision among accepted entity candidates that received human review."""
    reviewed = [
        entity
        for _, entity in _accepted_entities(fixtures)
        if entity.reviewed_correct is not None
    ]
    return RatioMetric(
        numerator=sum(entity.reviewed_correct is True for entity in reviewed),
        denominator=len(reviewed),
    )


def summarize_relation_semantic_precision(
    fixtures: list[QualityFixture],
) -> RatioMetric:
    """Semantic precision among accepted relations that received human review."""
    reviewed = [
        relation
        for relation in _accepted_relations(fixtures)
        if relation.semantically_correct is not None
    ]
    return RatioMetric(
        numerator=sum(relation.semantically_correct is True for relation in reviewed),
        denominator=len(reviewed),
    )


def summarize_provenance_completeness(
    fixtures: list[QualityFixture],
) -> RatioMetric:
    """Evidence coverage over every accepted entity and relation in the fixture."""
    candidates = [
        entity for _, entity in _accepted_entities(fixtures)
    ] + _accepted_relations(fixtures)
    return RatioMetric(
        numerator=sum(item.evidence_present for item in candidates),
        denominator=len(candidates),
    )


def summarize_entity_review_coverage(fixtures: list[QualityFixture]) -> RatioMetric:
    reviewed = sum(
        entity.reviewed_correct is not None
        for _, entity in _accepted_entities(fixtures)
    )
    population = sum(
        fixture.review_scope.accepted_entity_population for fixture in fixtures
    )
    return RatioMetric(reviewed, population)


def summarize_relation_review_coverage(fixtures: list[QualityFixture]) -> RatioMetric:
    reviewed = sum(
        relation.semantically_correct is not None
        for relation in _accepted_relations(fixtures)
    )
    population = sum(
        fixture.review_scope.accepted_relation_population for fixture in fixtures
    )
    return RatioMetric(reviewed, population)


def entity_review_candidate_ids(fixtures: list[QualityFixture]) -> tuple[str, ...]:
    """Unmatched accepted entities stay review candidates until a human labels them."""
    return tuple(
        sorted(
            entity.entity_id
            for _, entity in _accepted_entities(fixtures)
            if not entity.matched_gold and entity.reviewed_correct is None
        )
    )


def relation_review_candidate_ids(fixtures: list[QualityFixture]) -> tuple[str, ...]:
    return tuple(
        sorted(
            relation.relation_id
            for relation in _accepted_relations(fixtures)
            if not relation.matched_gold and relation.semantically_correct is None
        )
    )


def graph_structure_diagnostics(
    fixtures: list[QualityFixture],
    *,
    low_confidence_threshold: float,
    generic_names: set[str],
    hub_degree_threshold: int,
) -> StructuralDiagnostics:
    """Describe the accepted fixture graph without requiring Neo4j."""
    if not 0.0 <= low_confidence_threshold <= 1.0:
        raise ValueError("low_confidence_threshold must be between 0 and 1")
    if hub_degree_threshold < 1:
        raise ValueError("hub_degree_threshold must be positive")

    entity_rows = _accepted_entities(fixtures)
    entities = {entity.entity_id: entity for _, entity in entity_rows}
    if len(entities) != len(entity_rows):
        raise ValueError("accepted entity_id values must be globally unique")

    adjacency = {entity_id: set() for entity_id in entities}
    relations = _accepted_relations(fixtures)
    relation_ids = [relation.relation_id for relation in relations]
    if len(relation_ids) != len(set(relation_ids)):
        raise ValueError("accepted relation_id values must be globally unique")

    for relation in relations:
        source = relation.source_entity_id
        target = relation.target_entity_id
        if source not in adjacency or target not in adjacency:
            raise ValueError(f"accepted relation {relation.relation_id} has unknown endpoint")
        adjacency[source].add(target)
        adjacency[target].add(source)

    normalized_documents: dict[str, set[str]] = {}
    for sample_id, entity in entity_rows:
        normalized_documents.setdefault(entity.name.lower().strip(), set()).add(sample_id)
    duplicates = {
        name: tuple(sorted(sample_ids))
        for name, sample_ids in sorted(normalized_documents.items())
        if len(sample_ids) > 1
    }

    unseen = set(adjacency)
    component_sizes: list[int] = []
    while unseen:
        pending = [min(unseen)]
        unseen.remove(pending[0])
        size = 0
        while pending:
            current = pending.pop()
            size += 1
            neighbors = adjacency[current] & unseen
            pending.extend(sorted(neighbors, reverse=True))
            unseen.difference_update(neighbors)
        component_sizes.append(size)

    normalized_generic_names = {name.lower().strip() for name in generic_names}
    suspicious_hubs = tuple(
        sorted(
            entity_id
            for entity_id, entity in entities.items()
            if entity.name.lower().strip() in normalized_generic_names
            and len(adjacency[entity_id]) >= hub_degree_threshold
        )
    )
    return StructuralDiagnostics(
        isolated_entity_ids=tuple(
            sorted(entity_id for entity_id, neighbors in adjacency.items() if not neighbors)
        ),
        degree_one_entity_ids=tuple(
            sorted(
                entity_id for entity_id, neighbors in adjacency.items() if len(neighbors) == 1
            )
        ),
        low_confidence_relation_ids=tuple(
            sorted(
                relation.relation_id
                for relation in relations
                if relation.confidence < low_confidence_threshold
            )
        ),
        duplicate_normalized_names=duplicates,
        component_sizes=tuple(sorted(component_sizes, reverse=True)),
        suspicious_generic_hub_ids=suspicious_hubs,
    )
