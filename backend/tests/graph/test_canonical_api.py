"""Fake-driver API tests for the explicit canonical graph namespace."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.runs import RunStore


class _Record(dict):
    def data(self) -> dict:
        return dict(self)


class _MarkerDriver:
    def __init__(self, responses: dict[str, list[dict]]):
        self.responses = responses
        self.calls: list[tuple[str, dict]] = []

    def execute_query(self, query: str, **params):
        self.calls.append((query, params))
        if "DETACH DELETE" in query:
            return [], None, None
        marker = next(
            (name for name in self.responses if f"/* {name} */" in query),
            None,
        )
        if marker is None:
            raise AssertionError(f"unrecognized canonical query: {query[:100]}")
        return [_Record(row) for row in self.responses[marker]], None, None


@pytest.fixture
def neo4j_driver():
    """Keep this module independent from the real Neo4j fixture."""

    return _MarkerDriver({})


def _client(driver: _MarkerDriver) -> TestClient:
    app = create_app()
    app.state.neo4j = driver
    app.state.runs = RunStore()
    return TestClient(app)


def _coverage() -> dict:
    return {
        "source_entity_count": 3,
        "accepted_source_entity_count": 2,
        "review_source_entity_count": 1,
        "unresolved_source_entity_count": 0,
        "source_relation_count": 2,
        "projected_source_relation_count": 2,
        "excluded_relation_count": 0,
        "collapsed_self_relation_count": 0,
    }


def _nodes() -> list[dict]:
    return [
        {
            "canonical_id": "canonical:a",
            "canonical_name": "Alpha",
            "entity_type": "Concept",
            "document_ids": ["doc-b", "doc-a"],
            "source_names": ["ALPHA", "Alpha"],
            "source_entity_count": 2,
            "mention_count": 3,
        },
        {
            "canonical_id": "canonical:b",
            "canonical_name": "Beta",
            "entity_type": "Method",
            "document_ids": ["doc-a"],
            "source_names": ["Beta"],
            "source_entity_count": 1,
            "mention_count": 1,
        },
    ]


def _facts() -> list[dict]:
    return [
        {
            "source_canonical_id": "canonical:a",
            "target_canonical_id": "canonical:b",
            "type": "使用",
            "confidence": 0.9,
            "support_count": 2,
            "evidence_count": 2,
            "evidence": [
                {
                    "chunk_id": "doc-a#0",
                    "document_id": "doc-a",
                    "source_entity_id": "doc-a::alpha",
                    "target_entity_id": "doc-a::beta",
                    "confidence": 0.9,
                },
                {
                    "chunk_id": "doc-b#0",
                    "document_id": "doc-b",
                    "source_entity_id": "doc-b::alpha",
                    "target_entity_id": "doc-b::beta",
                    "confidence": 0.7,
                },
            ],
        }
    ]


def _driver() -> _MarkerDriver:
    return _MarkerDriver(
        {
            "canonical_coverage": [_coverage()],
            "canonical_nodes": _nodes(),
            "canonical_facts": _facts(),
            "canonical_search": [_nodes()[0]],
            "canonical_degrees": [
                {"canonical_id": "canonical:a", "degree": 1}
            ],
        }
    )


def test_canonical_communities_return_coverage_bounds_and_stable_identity():
    driver = _driver()
    response = _client(driver).get(
        "/api/graph/canonical/communities",
        params={
            "limit": 5,
            "nodeLimit": 20,
            "edgeLimit": 30,
            "evidenceLimit": 2,
            "documentId": "doc-a",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["coverage"] == {
        "sourceEntityCount": 3,
        "acceptedSourceEntityCount": 2,
        "reviewSourceEntityCount": 1,
        "unresolvedSourceEntityCount": 0,
        "sourceRelationCount": 2,
        "projectedSourceRelationCount": 2,
        "excludedRelationCount": 0,
        "collapsedSelfRelationCount": 0,
    }
    assert body["communities"][0]["representativeNode"]["identity"] == "canonical"
    assert body["communities"][0]["totalSupport"] == 2
    assert body["metadata"] == {
        "limit": 5,
        "nodeLimit": 20,
        "edgeLimit": 30,
        "evidenceLimit": 2,
        "communityCount": 1,
        "nodeCount": 2,
        "edgeCount": 1,
        "evidenceCount": 2,
        "truncated": False,
    }

    calls = {
        marker: (query, params)
        for query, params in driver.calls
        for marker in (
            "canonical_coverage",
            "canonical_nodes",
            "canonical_facts",
        )
        if f"/* {marker} */" in query
    }
    assert calls["canonical_coverage"][1]["min_confidence"] == 0.5
    assert calls["canonical_coverage"][1]["document_id"] == "doc-a"
    fact_query = calls["canonical_facts"][0]
    assert fact_query.count("RESOLVES_TO") >= 2
    assert "relation_evidence" in fact_query
    assert fact_query.count("MENTIONS") >= 4
    assert not any(
        token in fact_query.upper() for token in (" CREATE ", " MERGE ", " DELETE ", " SET ")
    )


def test_canonical_subgraph_is_bounded_and_preserves_all_returned_evidence():
    driver = _driver()
    response = _client(driver).get(
        "/api/graph/canonical/entities/canonical%3Aa/subgraph",
        params={
            "depth": 1,
            "nodeLimit": 2,
            "edgeLimit": 1,
            "evidenceLimit": 2,
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["centerId"] == "canonical:a"
    assert [node["id"] for node in body["nodes"]] == ["canonical:a", "canonical:b"]
    assert body["edges"][0]["id"].startswith("canonical-edge:v1:")
    assert body["edges"][0]["supportCount"] == 2
    assert body["edges"][0]["evidenceCount"] == 2
    assert [item["documentId"] for item in body["edges"][0]["evidence"]] == [
        "doc-a",
        "doc-b",
    ]
    assert body["metadata"] == {
        "depth": 1,
        "nodeLimit": 2,
        "edgeLimit": 1,
        "evidenceLimit": 2,
        "nodeCount": 2,
        "edgeCount": 1,
        "evidenceCount": 2,
        "truncated": False,
    }


def test_canonical_subgraph_missing_center_is_404():
    driver = _MarkerDriver(
        {
            "canonical_coverage": [_coverage()],
            "canonical_nodes": _nodes(),
            "canonical_facts": _facts(),
        }
    )
    response = _client(driver).get(
        "/api/graph/canonical/entities/missing/subgraph"
    )

    assert response.status_code == 404


def test_canonical_search_matches_alias_scope_and_returns_canonical_nodes():
    driver = _driver()
    response = _client(driver).get(
        "/api/graph/canonical/search",
        params={"q": "alpha", "limit": 10, "documentId": "doc-a"},
    )

    assert response.status_code == 200, response.text
    assert response.json()[0] == {
        "id": "canonical:a",
        "name": "Alpha",
        "type": "Concept",
        "identity": "canonical",
        "documentIds": ["doc-a", "doc-b"],
        "sourceEntityCount": 2,
        "mentionCount": 3,
        "aliases": ["ALPHA", "Alpha"],
        "aliasCount": 2,
        "aliasesTruncated": False,
        "degree": 1,
    }
    query, params = next(
        (query, params)
        for query, params in driver.calls
        if "/* canonical_search */" in query
    )
    assert "source.name" in query
    assert "canonical.canonical_name" in query
    assert params["q"] == "alpha"
    assert params["document_id"] == "doc-a"
    degree_query, degree_params = next(
        (query, params)
        for query, params in driver.calls
        if "/* canonical_degrees */" in query
    )
    assert degree_query.count("RESOLVES_TO") >= 2
    assert degree_params["canonical_ids"] == ["canonical:a"]
    assert degree_params["min_confidence"] == 0.5


@pytest.mark.parametrize(
    ("path", "params"),
    [
        ("/api/graph/canonical/communities", {"edgeLimit": 1001}),
        ("/api/graph/canonical/communities", {"evidenceLimit": 21}),
        (
            "/api/graph/canonical/entities/canonical%3Aa/subgraph",
            {"depth": 5},
        ),
        (
            "/api/graph/canonical/entities/canonical%3Aa/subgraph",
            {"edgeLimit": 201},
        ),
    ],
)
def test_canonical_routes_reject_out_of_contract_bounds(path: str, params: dict):
    response = _client(_driver()).get(path, params=params)
    assert response.status_code == 422
