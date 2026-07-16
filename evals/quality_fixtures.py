"""Deterministic labeled fixtures for graph extraction quality checks."""

import json
from pathlib import Path

from pydantic import BaseModel, Field, model_validator


class GoldEntity(BaseModel):
    name: str
    type: str


class CandidateEntity(BaseModel):
    entity_id: str
    name: str
    type: str
    accepted: bool
    matched_gold: bool
    reviewed_correct: bool | None
    evidence_present: bool


class GoldRelation(BaseModel):
    source: str
    type: str
    target: str


class CandidateRelation(BaseModel):
    relation_id: str
    source_entity_id: str
    target_entity_id: str
    source: str
    type: str
    target: str
    accepted: bool
    matched_gold: bool
    semantically_correct: bool | None
    evidence_present: bool
    confidence: float = Field(ge=0.0, le=1.0)


class ReviewScope(BaseModel):
    accepted_entity_population: int = Field(ge=0)
    accepted_relation_population: int = Field(ge=0)
    selection_method: str = Field(min_length=1)


class QualityFixture(BaseModel):
    sample_id: str
    text_kind: str
    review_scope: ReviewScope
    gold_entities: list[GoldEntity]
    gold_relations: list[GoldRelation]
    candidate_entities: list[CandidateEntity]
    candidate_relations: list[CandidateRelation]

    @model_validator(mode="after")
    def validate_graph_and_scope(self) -> "QualityFixture":
        entity_ids = [item.entity_id for item in self.candidate_entities]
        if len(entity_ids) != len(set(entity_ids)):
            raise ValueError("candidate entity_id values must be unique within a fixture")

        relation_ids = [item.relation_id for item in self.candidate_relations]
        if len(relation_ids) != len(set(relation_ids)):
            raise ValueError("candidate relation_id values must be unique within a fixture")

        known_entity_ids = set(entity_ids)
        accepted_entity_ids = {
            item.entity_id for item in self.candidate_entities if item.accepted
        }
        for relation in self.candidate_relations:
            endpoints = {relation.source_entity_id, relation.target_entity_id}
            if not endpoints <= known_entity_ids:
                raise ValueError(
                    f"relation {relation.relation_id} references an unknown entity"
                )
            if relation.accepted and not endpoints <= accepted_entity_ids:
                raise ValueError(
                    f"accepted relation {relation.relation_id} must use accepted entities"
                )

        accepted_entity_count = len(accepted_entity_ids)
        accepted_relation_count = sum(
            item.accepted for item in self.candidate_relations
        )
        if self.review_scope.accepted_entity_population < accepted_entity_count:
            raise ValueError("declared entity population is smaller than fixture candidates")
        if self.review_scope.accepted_relation_population < accepted_relation_count:
            raise ValueError("declared relation population is smaller than fixture candidates")
        return self


def load_quality_fixtures(path: Path | None = None) -> list[QualityFixture]:
    """Load non-empty JSONL rows into validated quality fixtures."""
    fixture_path = path or Path(__file__).with_name("quality_fixtures.jsonl")
    rows: list[QualityFixture] = []
    with fixture_path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(QualityFixture.model_validate(json.loads(line)))
    return rows
