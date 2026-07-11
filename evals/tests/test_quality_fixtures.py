import json

from evals.quality_fixtures import load_quality_fixtures


def _valid_row() -> dict:
    return {
        "sample_id": "tmp",
        "text_kind": "prose",
        "gold_entities": [{"name": "Neo4j", "type": "技术"}],
        "gold_relations": [],
        "candidate_entities": [
            {"name": "Neo4j", "type": "技术", "accepted": True, "evidence_present": True}
        ],
        "candidate_relations": [],
    }


def test_quality_fixture_has_gold_and_negative_candidates():
    rows = load_quality_fixtures()

    assert rows
    assert rows[0].gold_entities
    assert any(not item.accepted for item in rows[0].candidate_entities)
    assert any(not item.semantically_correct for item in rows[0].candidate_relations)
    assert any(not item.evidence_present for item in rows[0].candidate_entities)


def test_fixture_loader_ignores_blank_lines_and_validates_jsonl(tmp_path):
    path = tmp_path / "fixtures.jsonl"
    path.write_text("\n" + json.dumps(_valid_row(), ensure_ascii=False) + "\n", encoding="utf-8")

    assert len(load_quality_fixtures(path)) == 1
