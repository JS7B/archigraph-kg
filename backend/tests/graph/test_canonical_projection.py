"""Pure-domain tests for the read-time canonical graph projection."""

from __future__ import annotations

import random

import pytest

from tests.graph import test_canonical_projection_live as live_projection

from app.graph.models import ProjectionCoverage
from app.graph.projection import (
    aggregate_projection,
    bounded_bfs,
    deterministic_communities,
)


class _NoopDriver:
    def execute_query(self, query: str, **params):
        return [], None, None


@pytest.fixture
def neo4j_driver():
    """Keep pure-domain tests independent from the integration fixture."""

    return _NoopDriver()


def _node(
    canonical_id: str,
    *,
    documents: list[str] | None = None,
    source_names: list[str] | None = None,
    source_count: int = 1,
    mention_count: int = 1,
) -> dict:
    return {
        "canonical_id": canonical_id,
        "canonical_name": canonical_id.upper(),
        "entity_type": "Concept",
        "document_ids": documents or ["doc-a"],
        "source_names": source_names or [canonical_id.upper()],
        "source_entity_count": source_count,
        "mention_count": mention_count,
    }


def _fact(
    source: str,
    target: str,
    relation_type: str,
    *,
    document_id: str,
    chunk_id: str,
    source_entity_id: str,
    target_entity_id: str,
    confidence: float = 0.8,
) -> dict:
    return {
        "source_canonical_id": source,
        "target_canonical_id": target,
        "type": relation_type,
        "confidence": confidence,
        "document_id": document_id,
        "chunk_id": chunk_id,
        "source_entity_id": source_entity_id,
        "target_entity_id": target_entity_id,
    }


def _coverage(**updates: int) -> ProjectionCoverage:
    values = {
        "source_entity_count": 4,
        "accepted_source_entity_count": 4,
        "review_source_entity_count": 0,
        "unresolved_source_entity_count": 0,
        "source_relation_count": 4,
        "projected_source_relation_count": 4,
        "excluded_relation_count": 0,
        "collapsed_self_relation_count": 0,
    }
    values.update(updates)
    return ProjectionCoverage(**values)


def test_cross_document_facts_aggregate_with_stable_evidence_and_id():
    node_rows = [
        _node("canonical-a", documents=["doc-b", "doc-a"]),
        _node("canonical-b", documents=["doc-b", "doc-a"]),
    ]
    facts = [
        _fact(
            "canonical-a",
            "canonical-b",
            "使用",
            document_id="doc-b",
            chunk_id="doc-b#2",
            source_entity_id="doc-b::a",
            target_entity_id="doc-b::b",
            confidence=0.7,
        ),
        _fact(
            "canonical-a",
            "canonical-b",
            "使用",
            document_id="doc-a",
            chunk_id="doc-a#1",
            source_entity_id="doc-a::a",
            target_entity_id="doc-a::b",
            confidence=0.9,
        ),
    ]

    first = aggregate_projection(
        node_rows,
        facts,
        _coverage(source_relation_count=2, projected_source_relation_count=2),
        node_limit=10,
        edge_limit=10,
        evidence_limit=10,
    )
    random.Random(7).shuffle(node_rows)
    random.Random(9).shuffle(facts)
    second = aggregate_projection(
        node_rows,
        facts,
        first.coverage,
        node_limit=10,
        edge_limit=10,
        evidence_limit=10,
    )

    assert first == second
    assert len(first.edges) == 1
    edge = first.edges[0]
    assert edge.id.startswith("canonical-edge:v1:")
    assert edge.support_count == edge.evidence_count == 2
    assert edge.confidence == 0.9
    assert [item.document_id for item in edge.evidence] == ["doc-a", "doc-b"]
    assert edge.evidence_truncated is False
    assert first.nodes[0].document_ids == ["doc-a", "doc-b"]


def test_direction_type_and_self_relation_contract_remain_explicit():
    facts = [
        _fact(
            "a",
            "b",
            "使用",
            document_id="d",
            chunk_id="d#0",
            source_entity_id="d::a",
            target_entity_id="d::b",
        ),
        _fact(
            "b",
            "a",
            "使用",
            document_id="d",
            chunk_id="d#1",
            source_entity_id="d::b",
            target_entity_id="d::a",
        ),
        _fact(
            "a",
            "b",
            "依赖",
            document_id="d",
            chunk_id="d#2",
            source_entity_id="d::a",
            target_entity_id="d::b",
        ),
        _fact(
            "a",
            "a",
            "属于",
            document_id="d",
            chunk_id="d#3",
            source_entity_id="d::a-1",
            target_entity_id="d::a-2",
        ),
    ]
    coverage = _coverage(
        projected_source_relation_count=3,
        collapsed_self_relation_count=1,
    )

    snapshot = aggregate_projection(
        [_node("a"), _node("b")],
        facts,
        coverage,
        node_limit=10,
        edge_limit=10,
        evidence_limit=10,
    )

    assert {(edge.source, edge.target, edge.type) for edge in snapshot.edges} == {
        ("a", "b", "使用"),
        ("b", "a", "使用"),
        ("a", "b", "依赖"),
    }
    assert snapshot.coverage.collapsed_self_relation_count == 1


def test_alias_evidence_and_response_limits_are_exact():
    facts = [
        _fact(
            "a",
            "b",
            "使用",
            document_id=f"doc-{index}",
            chunk_id=f"doc-{index}#0",
            source_entity_id=f"doc-{index}::a",
            target_entity_id=f"doc-{index}::b",
        )
        for index in range(3)
    ]
    snapshot = aggregate_projection(
        [
            _node("a", source_names=["Zed", "A", "Alias-2", "Alias-1"]),
            _node("b"),
            _node("c"),
        ],
        facts,
        _coverage(source_relation_count=3, projected_source_relation_count=3),
        node_limit=2,
        edge_limit=1,
        evidence_limit=2,
        alias_limit=2,
    )

    assert [node.id for node in snapshot.nodes] == ["a", "b"]
    assert snapshot.nodes[0].aliases == ["A", "Alias-1"]
    assert snapshot.nodes[0].alias_count == 4
    assert snapshot.nodes[0].aliases_truncated is True
    assert snapshot.edges[0].evidence_count == 3
    assert len(snapshot.edges[0].evidence) == 2
    assert snapshot.edges[0].evidence_truncated is True
    assert snapshot.node_truncated is True
    assert snapshot.evidence_truncated is True


def test_preferred_center_survives_node_probe_and_edge_limit_reports_truncation():
    facts = [
        _fact(
            "a",
            "z",
            relation_type,
            document_id="d",
            chunk_id=f"d#{index}",
            source_entity_id="d::a",
            target_entity_id="d::z",
        )
        for index, relation_type in enumerate(("使用", "依赖"))
    ]

    snapshot = aggregate_projection(
        [_node("a"), _node("b"), _node("z")],
        facts,
        _coverage(source_relation_count=2, projected_source_relation_count=2),
        node_limit=2,
        edge_limit=1,
        evidence_limit=5,
        preferred_node_id="z",
    )

    assert [node.id for node in snapshot.nodes] == ["z", "a"]
    assert len(snapshot.edges) == 1
    assert snapshot.total_edge_count == 2
    assert snapshot.node_truncated is True
    assert snapshot.edge_truncated is True


def test_modularity_partition_splits_bridge_connected_topics_deterministically():
    nodes = [_node(node_id) for node_id in ("a", "b", "c", "x", "y", "z")]
    facts: list[dict] = []
    for source, target in (
        ("a", "b"),
        ("a", "c"),
        ("b", "c"),
        ("x", "y"),
        ("x", "z"),
        ("y", "z"),
    ):
        facts.append(
            _fact(
                source,
                target,
                "相关",
                document_id="d",
                chunk_id=f"d#{source}{target}",
                source_entity_id=f"d::{source}",
                target_entity_id=f"d::{target}",
                confidence=0.9,
            )
        )
    facts.append(
        _fact(
            "c",
            "x",
            "相关",
            document_id="d",
            chunk_id="d#bridge",
            source_entity_id="d::c",
            target_entity_id="d::x",
            confidence=0.6,
        )
    )
    snapshot = aggregate_projection(
        nodes,
        facts,
        _coverage(source_relation_count=7, projected_source_relation_count=7),
        node_limit=20,
        edge_limit=20,
        evidence_limit=2,
    )

    first = deterministic_communities(snapshot.nodes, snapshot.edges, limit=20)
    second = deterministic_communities(
        list(reversed(snapshot.nodes)), list(reversed(snapshot.edges)), limit=20
    )

    assert first == second
    assert len(first) == 2
    assert {item.node_count for item in first} == {3}
    assert all(item.id.startswith("community:v1:") for item in first)


def test_bounded_bfs_is_depth_and_limit_exact():
    facts = [
        _fact(
            source,
            target,
            "相关",
            document_id="d",
            chunk_id=f"d#{index}",
            source_entity_id=f"d::{source}",
            target_entity_id=f"d::{target}",
        )
        for index, (source, target) in enumerate(
            (("a", "b"), ("b", "c"), ("c", "d"), ("a", "e"))
        )
    ]
    snapshot = aggregate_projection(
        [_node(node_id) for node_id in ("a", "b", "c", "d", "e")],
        facts,
        _coverage(),
        node_limit=20,
        edge_limit=20,
        evidence_limit=5,
    )

    one_hop = bounded_bfs(
        snapshot, center_id="a", depth=1, node_limit=10, edge_limit=10
    )
    assert {node.id for node in one_hop.nodes} == {"a", "b", "e"}
    assert len(one_hop.edges) == 2

    limited = bounded_bfs(
        snapshot, center_id="a", depth=3, node_limit=3, edge_limit=2
    )
    assert len(limited.nodes) == 3
    assert len(limited.edges) == 2
    assert limited.truncated is True


def test_explicit_live_uri_connection_failure_is_not_skipped(monkeypatch):
    class _BrokenDriver:
        closed = False

        def verify_connectivity(self):
            raise RuntimeError("explicit live database is unavailable")

        def close(self):
            self.closed = True

    driver = _BrokenDriver()
    monkeypatch.setattr(
        live_projection.GraphDatabase,
        "driver",
        lambda *args, **kwargs: driver,
    )

    with pytest.raises(RuntimeError, match="explicit live database is unavailable"):
        live_projection._connect_explicit_driver(
            "bolt://invalid.example:7687",
            "neo4j",
            "password",
        )

    assert driver.closed is True
