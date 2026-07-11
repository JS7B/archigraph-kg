"""Focused fake-driver tests for the deterministic community overview."""

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


def test_communities_returns_stable_component_summaries_and_passes_bounds():
    driver = _FakeDriver(
        [
            {
                "nodes": [
                    {
                        "entity_id": "ent-c",
                        "name": "C",
                        "entity_type": "Concept",
                        "document_id": "doc-b",
                    },
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
                        "source": "ent-b",
                        "target": "ent-a",
                        "type": "uses",
                        "confidence": 0.9,
                    }
                ],
            }
        ]
    )

    response = _client(driver).get(
        "/api/graph/communities",
        params={"limit": 5, "nodeLimit": 20, "documentId": "doc-a"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body == [
        {
            "id": "community-ent-a",
            "representativeNode": {
                "id": "ent-a",
                "name": "A",
                "type": "Concept",
                "documentId": "doc-a",
            },
            "nodeCount": 2,
            "edgeCount": 1,
            "documentIds": ["doc-a"],
        },
        {
            "id": "community-ent-c",
            "representativeNode": {
                "id": "ent-c",
                "name": "C",
                "type": "Concept",
                "documentId": "doc-b",
            },
            "nodeCount": 1,
            "edgeCount": 0,
            "documentIds": ["doc-b"],
        },
    ]

    query, params = driver.calls[0]
    assert params["limit"] == 5
    assert params["node_limit"] == 20
    assert params["document_id"] == "doc-a"
    assert "$node_limit" in query
    assert "$document_id" in query


def test_communities_empty_graph_returns_empty_list():
    response = _client(_FakeDriver([])).get("/api/graph/communities")

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize(
    "query",
    [
        {"limit": 0},
        {"limit": 101},
        {"nodeLimit": 0},
        {"nodeLimit": 501},
    ],
)
def test_communities_rejects_invalid_bounds(query: dict[str, int]):
    response = _client(_FakeDriver([])).get(
        "/api/graph/communities", params=query
    )

    assert response.status_code == 422
