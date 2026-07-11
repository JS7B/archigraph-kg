"""Fake-driver tests for document-scoped graph reads and evidence mapping."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.runs import RunStore


class _Record:
    def __init__(self, payload: dict):
        self._payload = payload

    def data(self) -> dict:
        return self._payload

    def __getitem__(self, key: str):
        return self._payload[key]


class _SequenceDriver:
    def __init__(self, responses: list[list[dict]]):
        self.responses = responses
        self.calls: list[tuple[str, dict]] = []

    def execute_query(self, query: str, **params):
        self.calls.append((query, params))
        rows = self.responses.pop(0) if self.responses else []
        return [_Record(row) for row in rows], None, None


@pytest.fixture
def neo4j_driver():
    """Override the integration fixture so this module remains unit-only."""

    return _SequenceDriver([])


def _client(driver: _SequenceDriver) -> TestClient:
    app = create_app()
    app.state.neo4j = driver
    app.state.runs = RunStore()
    return TestClient(app)


def test_list_entities_filters_document_and_preserves_edge_evidence():
    driver = _SequenceDriver(
        [
            [
                {
                    "entity_id": "ent-a",
                    "name": "A",
                    "entity_type": "Concept",
                    "document_id": "doc-a",
                    "mention_count": 1,
                    "degree": 1,
                },
                {
                    "entity_id": "ent-b",
                    "name": "B",
                    "entity_type": "Method",
                    "document_id": "doc-a",
                    "mention_count": 1,
                    "degree": 1,
                },
            ],
            [
                {
                    "source": "ent-a",
                    "target": "ent-b",
                    "type": "uses",
                    "confidence": 0.9,
                    "evidence_chunk_id": "doc-a#0",
                },
                {
                    "source": "ent-a",
                    "target": "ent-c",
                    "type": "unknown",
                    "confidence": None,
                    "evidence_chunk_id": None,
                },
            ],
        ]
    )

    response = _client(driver).get(
        "/api/graph/entities", params={"limit": 10, "documentId": "doc-a"}
    )

    assert response.status_code == 200, response.text
    assert response.json()["edges"] == [
        {
            "source": "ent-a",
            "target": "ent-b",
            "type": "uses",
            "confidence": 0.9,
            "evidenceChunkId": "doc-a#0",
        }
    ]
    assert len(driver.calls) == 2
    assert all(call[1]["document_id"] == "doc-a" for call in driver.calls)
    assert all("$document_id" in call[0] for call in driver.calls)


def test_neighbors_filters_document_and_maps_missing_evidence_to_none():
    driver = _SequenceDriver(
        [
            [
                {
                    "nodes": [
                        {
                            "entity_id": "ent-a",
                            "name": "A",
                            "entity_type": "Concept",
                            "document_id": "doc-a",
                        }
                    ],
                    "edges": [
                        {
                            "source": "ent-a",
                            "target": "ent-a",
                            "type": "self",
                            "confidence": None,
                            "evidence_chunk_id": None,
                        }
                    ],
                }
            ]
        ]
    )

    response = _client(driver).get(
        "/api/graph/entities/ent-a/neighbors", params={"document_id": "doc-a"}
    )

    assert response.status_code == 200, response.text
    assert response.json()["edges"][0]["evidenceChunkId"] is None
    query, params = driver.calls[0]
    assert params["document_id"] == "doc-a"
    assert "$document_id" in query


def test_search_filters_document_without_changing_node_shape():
    driver = _SequenceDriver(
        [
            [
                {
                    "entity_id": "ent-a",
                    "name": "A",
                    "entity_type": "Concept",
                    "document_id": "doc-a",
                }
            ]
        ]
    )

    response = _client(driver).get(
        "/api/graph/search", params={"q": "a", "documentId": "doc-a"}
    )

    assert response.status_code == 200, response.text
    assert response.json() == [
        {"id": "ent-a", "name": "A", "type": "Concept", "documentId": "doc-a"}
    ]
    query, params = driver.calls[0]
    assert params["document_id"] == "doc-a"
    assert "$document_id" in query


def test_graph_devlog_has_all_five_learning_fields():
    text = Path(__file__).parents[2].joinpath("DEVLOG.md").read_text(encoding="utf-8")
    latest = text.rsplit("## ", 1)[-1]
    for field in ("做了什么", "这是什么", "为什么需要", "为什么这么做", "踩了什么坑"):
        assert f"- {field}：" in latest
