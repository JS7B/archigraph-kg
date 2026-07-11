"""Deterministic labeled fixtures for graph extraction quality checks."""

import json
from pathlib import Path

from pydantic import BaseModel


class GoldEntity(BaseModel):
    name: str
    type: str


class CandidateEntity(BaseModel):
    name: str
    type: str
    accepted: bool
    evidence_present: bool


class GoldRelation(BaseModel):
    source: str
    type: str
    target: str


class CandidateRelation(BaseModel):
    source: str
    type: str
    target: str
    accepted: bool
    semantically_correct: bool


class QualityFixture(BaseModel):
    sample_id: str
    text_kind: str
    gold_entities: list[GoldEntity]
    gold_relations: list[GoldRelation]
    candidate_entities: list[CandidateEntity]
    candidate_relations: list[CandidateRelation]


def load_quality_fixtures(path: Path | None = None) -> list[QualityFixture]:
    """Load non-empty JSONL rows into validated quality fixtures."""
    fixture_path = path or Path(__file__).with_name("quality_fixtures.jsonl")
    rows: list[QualityFixture] = []
    with fixture_path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(QualityFixture.model_validate(json.loads(line)))
    return rows
