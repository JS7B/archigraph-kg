import json

import pytest
from pydantic import ValidationError

from evals.quality_fixtures import load_quality_fixtures


def _valid_row() -> dict:
    return {
        "sample_id": "tmp",
        "text_kind": "prose",
        "review_scope": {
            "accepted_entity_population": 1,
            "accepted_relation_population": 0,
            "selection_method": "complete fixture review",
        },
        "gold_entities": [{"name": "Neo4j", "type": "技术"}],
        "gold_relations": [],
        "candidate_entities": [
            {
                "entity_id": "tmp::neo4j",
                "name": "Neo4j",
                "type": "技术",
                "accepted": True,
                "matched_gold": True,
                "reviewed_correct": True,
                "evidence_present": True,
            }
        ],
        "candidate_relations": [],
    }


def test_quality_fixture_has_gold_and_negative_candidates():
    rows = load_quality_fixtures()

    entities = [item for row in rows for item in row.candidate_entities if item.accepted]
    relations = [item for row in rows for item in row.candidate_relations if item.accepted]

    assert rows and all(row.gold_entities for row in rows)
    assert any(item.reviewed_correct is True for item in entities)
    assert any(item.reviewed_correct is False for item in entities)
    assert any(item.reviewed_correct is None and not item.matched_gold for item in entities)
    assert any(item.semantically_correct is True for item in relations)
    assert any(item.semantically_correct is False for item in relations)
    assert any(item.semantically_correct is None and not item.matched_gold for item in relations)
    assert all(item.evidence_present for item in [*entities, *relations])
    assert all(row.review_scope.selection_method for row in rows)


def test_fixture_loader_ignores_blank_lines_and_validates_jsonl(tmp_path):
    path = tmp_path / "fixtures.jsonl"
    path.write_text("\n" + json.dumps(_valid_row(), ensure_ascii=False) + "\n", encoding="utf-8")

    assert len(load_quality_fixtures(path)) == 1


@pytest.mark.parametrize(
    ("candidate_key", "missing_field"),
    [
        ("candidate_entities", "reviewed_correct"),
        ("candidate_entities", "evidence_present"),
    ],
)
def test_fixture_rejects_entity_missing_metric_label(
    tmp_path, candidate_key: str, missing_field: str
):
    row = _valid_row()
    del row[candidate_key][0][missing_field]
    path = tmp_path / "fixtures.jsonl"
    path.write_text(json.dumps(row), encoding="utf-8")

    with pytest.raises(ValidationError):
        load_quality_fixtures(path)


@pytest.mark.parametrize("missing_field", ["semantically_correct", "evidence_present"])
def test_fixture_rejects_relation_missing_semantic_or_provenance_label(
    tmp_path, missing_field: str
):
    row = _valid_row()
    row["review_scope"]["accepted_relation_population"] = 1
    row["candidate_relations"] = [
        {
            "relation_id": "tmp::uses",
            "source_entity_id": "tmp::neo4j",
            "target_entity_id": "tmp::neo4j",
            "source": "Neo4j",
            "type": "uses",
            "target": "Neo4j",
            "accepted": True,
            "matched_gold": False,
            "semantically_correct": True,
            "evidence_present": True,
            "confidence": 0.9,
        }
    ]
    del row["candidate_relations"][0][missing_field]
    path = tmp_path / "fixtures.jsonl"
    path.write_text(json.dumps(row), encoding="utf-8")

    with pytest.raises(ValidationError):
        load_quality_fixtures(path)


def test_fixture_rejects_relation_with_unknown_endpoint(tmp_path):
    row = _valid_row()
    row["review_scope"]["accepted_relation_population"] = 1
    row["candidate_relations"] = [
        {
            "relation_id": "tmp::uses",
            "source_entity_id": "tmp::neo4j",
            "target_entity_id": "tmp::missing",
            "source": "Neo4j",
            "type": "uses",
            "target": "Missing",
            "accepted": True,
            "matched_gold": False,
            "semantically_correct": None,
            "evidence_present": True,
            "confidence": 0.9,
        }
    ]
    path = tmp_path / "fixtures.jsonl"
    path.write_text(json.dumps(row), encoding="utf-8")

    with pytest.raises(ValidationError, match="unknown entity"):
        load_quality_fixtures(path)
