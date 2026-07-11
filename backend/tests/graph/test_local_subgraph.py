"""Focused fake-driver tests for the bounded local subgraph contract."""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.runs import RunStore


class _Record:
    def __init__(self, payload: dict):
        self._payload = payload

    def data(self) -> dict:
        return self._payload


class _FakeDriver:
    def __init__(self, rows: list[dict]):
        self.rows = rows
        self.calls: list[tuple[str, dict]] = []

    def execute_query(self, query: str, **params):
        self.calls.append((query, params))
        return [_Record(row) for row in self.rows], None, None


@pytest.fixture
def neo4j_driver():
    """Override the integration fixture so this module remains unit-only."""

    return _FakeDriver([])


def _client(driver: _FakeDriver) -> TestClient:
    app = create_app()
    app.state.neo4j = driver
    app.state.runs = RunStore()
    return TestClient(app)


def test_subgraph_returns_bounded_nodes_edges_and_evidence():
    driver = _FakeDriver(
        [
            {
                "center_id": "ent-a",
                "nodes": [
                    {
                        "entity_id": "ent-a",
                        "name": "A",
                        "entity_type": "Concept",
                        "document_id": "doc-a",
                    },
                    {
                        "entity_id": "ent-b",
                        "name": "B",
                        "entity_type": "Method",
                        "document_id": "doc-a",
                    },
                ],
                "edges": [
                    {
                        "source": "ent-a",
                        "target": "ent-b",
                        "type": "uses",
                        "confidence": 0.91,
                        "evidence_chunk_id": "doc-a#0",
                    }
                ],
                "node_count": 2,
                "edge_count": 1,
                "truncated": False,
            }
        ]
    )

    response = _client(driver).get(
        "/api/graph/entities/ent-a/subgraph",
        params={
            "depth": 2,
            "limit": 3,
            "document_id": "doc-a",
            "type": "Method",
            "min_confidence": 0.8,
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["centerId"] == "ent-a"
    assert body["nodes"][0] == {
        "id": "ent-a",
        "name": "A",
        "type": "Concept",
        "documentId": "doc-a",
    }
    assert body["edges"] == [
        {
            "source": "ent-a",
            "target": "ent-b",
            "type": "uses",
            "confidence": 0.91,
            "evidenceChunkId": "doc-a#0",
        }
    ]
    assert body["metadata"] == {
        "depth": 2,
        "limit": 3,
        "nodeCount": 2,
        "edgeCount": 1,
        "truncated": False,
    }

    query, params = driver.calls[0]
    assert params["entity_id"] == "ent-a"
    assert params["depth"] == 2
    assert params["limit"] == 3
    assert params["document_id"] == "doc-a"
    assert params["entity_type"] is None
    assert params["type"] == "Method"
    assert params["min_confidence"] == 0.8
    assert "$limit" in query
    assert "*1..4" in query


def test_subgraph_missing_center_returns_404():
    response = _client(_FakeDriver([])).get(
        "/api/graph/entities/missing/subgraph"
    )

    assert response.status_code == 404


@pytest.mark.parametrize(
    "query",
    [
        {"depth": 0},
        {"depth": 5},
        {"limit": 0},
        {"limit": 101},
    ],
)
def test_subgraph_rejects_unbounded_or_invalid_limits(query: dict[str, int]):
    response = _client(_FakeDriver([])).get(
        "/api/graph/entities/ent-a/subgraph", params=query
    )

    assert response.status_code == 422
