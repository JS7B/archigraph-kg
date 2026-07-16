"""Real-Neo4j lifecycle tests for the read-time canonical projection.

These tests run only when an explicitly isolated Wave 3 URI is supplied.  All
records use ``test_wave3_*`` provenance and cleanup remains prefix-scoped.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from neo4j import GraphDatabase

from app.graph.projection import CanonicalProjectionStore
from app.main import create_app
from app.runs import RunStore
from app.runs.tasks import _do_delete


def _connect_explicit_driver(uri: str, username: str, password: str):
    """Connect to an explicitly requested live gate or fail without skipping."""

    driver = GraphDatabase.driver(uri, auth=(username, password))
    try:
        driver.verify_connectivity()
    except Exception:
        driver.close()
        raise
    return driver


@pytest.fixture(scope="module")
def neo4j_driver():
    uri = os.getenv("WAVE3_NEO4J_URI")
    if not uri:
        pytest.skip("WAVE3_NEO4J_URI is not configured for isolated live tests")
    driver = _connect_explicit_driver(
        uri,
        os.getenv("WAVE3_NEO4J_USER", "neo4j"),
        os.getenv("WAVE3_NEO4J_PASSWORD", "wave3-test-password"),
    )
    yield driver
    driver.execute_query(
        """
        MATCH (node)
        WHERE node.document_id STARTS WITH 'test_wave3_'
           OR node.canonical_id STARTS WITH 'canonical:test_wave3_'
        DETACH DELETE node
        """,
        database_="neo4j",
    )
    driver.close()


@pytest.fixture(autouse=True)
def _clean_wave3_records(neo4j_driver):
    neo4j_driver.execute_query(
        """
        MATCH (node)
        WHERE node.document_id STARTS WITH 'test_wave3_'
           OR node.canonical_id STARTS WITH 'canonical:test_wave3_'
        DETACH DELETE node
        """,
        database_="neo4j",
    )
    yield
    neo4j_driver.execute_query(
        """
        MATCH (node)
        WHERE node.document_id STARTS WITH 'test_wave3_'
           OR node.canonical_id STARTS WITH 'canonical:test_wave3_'
        DETACH DELETE node
        """,
        database_="neo4j",
    )


def _seed_two_document_support(driver) -> tuple[str, str]:
    rows = [
        {
            "document_id": "test_wave3_doc_a",
            "chunk_id": "test_wave3_doc_a#0",
            "source_a": "test_wave3_doc_a::alpha",
            "source_b": "test_wave3_doc_a::beta",
            "confidence": 0.9,
        },
        {
            "document_id": "test_wave3_doc_b",
            "chunk_id": "test_wave3_doc_b#0",
            "source_a": "test_wave3_doc_b::alpha-alias",
            "source_b": "test_wave3_doc_b::beta",
            "confidence": 0.7,
        },
    ]
    canonical_a = "canonical:test_wave3_alpha"
    canonical_b = "canonical:test_wave3_beta"
    driver.execute_query(
        """
        MERGE (canonical_a:CanonicalEntity {canonical_id: $canonical_a})
          SET canonical_a.canonical_name = 'Alpha',
              canonical_a.normalized_name = 'alpha',
              canonical_a.entity_type = 'Concept',
              canonical_a.resolution_version = 'v1'
        MERGE (canonical_b:CanonicalEntity {canonical_id: $canonical_b})
          SET canonical_b.canonical_name = 'Beta',
              canonical_b.normalized_name = 'beta',
              canonical_b.entity_type = 'Method',
              canonical_b.resolution_version = 'v1'
        WITH canonical_a, canonical_b
        UNWIND $rows AS row
        MERGE (document:Document {document_id: row.document_id})
        MERGE (chunk:Chunk {chunk_id: row.chunk_id})
          SET chunk.document_id = row.document_id
        MERGE (document)-[:HAS_CHUNK]->(chunk)
        MERGE (source_a:Entity {entity_id: row.source_a})
          SET source_a.document_id = row.document_id,
              source_a.name = CASE
                WHEN row.document_id ENDS WITH '_b' THEN 'A-Prime'
                ELSE 'Alpha'
              END,
              source_a.entity_type = 'Concept',
              source_a.mention_count = 1
        MERGE (source_b:Entity {entity_id: row.source_b})
          SET source_b.document_id = row.document_id,
              source_b.name = 'Beta',
              source_b.entity_type = 'Method',
              source_b.mention_count = 1
        MERGE (chunk)-[:MENTIONS]->(source_a)
        MERGE (chunk)-[:MENTIONS]->(source_b)
        MERGE (source_a)-[resolution_a:RESOLVES_TO]->(canonical_a)
          SET resolution_a.method = 'exact',
              resolution_a.score = 1.0,
              resolution_a.reason = 'test',
              resolution_a.source_document_id = row.document_id,
              resolution_a.evidence_chunk_id = row.chunk_id
        MERGE (source_b)-[resolution_b:RESOLVES_TO]->(canonical_b)
          SET resolution_b.method = 'exact',
              resolution_b.score = 1.0,
              resolution_b.reason = 'test',
              resolution_b.source_document_id = row.document_id,
              resolution_b.evidence_chunk_id = row.chunk_id
        MERGE (source_a)-[relation:RELATES {
          type: '使用',
          evidence_chunk_id: row.chunk_id
        }]->(source_b)
          SET relation.confidence = row.confidence
        """,
        rows=rows,
        canonical_a=canonical_a,
        canonical_b=canonical_b,
        database_="neo4j",
    )
    return canonical_a, canonical_b


def _source_fingerprint(driver) -> list[dict]:
    records, _, _ = driver.execute_query(
        """
        MATCH (source:Entity)-[relationship]->(target)
        WHERE source.document_id STARTS WITH 'test_wave3_'
        RETURN source.entity_id AS source,
               type(relationship) AS relationship_type,
               coalesce(target.entity_id, target.canonical_id) AS target,
               properties(relationship) AS properties
        ORDER BY source, relationship_type, target
        """,
        database_="neo4j",
    )
    return [dict(record) for record in records]


def _graph_fingerprint(driver) -> dict[str, list[dict]]:
    node_records, _, _ = driver.execute_query(
        """
        MATCH (node)
        WHERE node.document_id STARTS WITH 'test_wave3_'
           OR node.canonical_id STARTS WITH 'canonical:test_wave3_'
        RETURN labels(node) AS labels,
               coalesce(
                 node.entity_id,
                 node.chunk_id,
                 node.canonical_id,
                 node.document_id
               ) AS identity,
               properties(node) AS properties
        ORDER BY identity, labels
        """,
        database_="neo4j",
    )
    relationship_records, _, _ = driver.execute_query(
        """
        MATCH (source)-[relationship]->(target)
        WHERE source.document_id STARTS WITH 'test_wave3_'
           OR source.canonical_id STARTS WITH 'canonical:test_wave3_'
           OR target.document_id STARTS WITH 'test_wave3_'
           OR target.canonical_id STARTS WITH 'canonical:test_wave3_'
        RETURN coalesce(
                 source.entity_id,
                 source.chunk_id,
                 source.canonical_id,
                 source.document_id
               ) AS source,
               type(relationship) AS relationship_type,
               coalesce(
                 target.entity_id,
                 target.chunk_id,
                 target.canonical_id,
                 target.document_id
               ) AS target,
               properties(relationship) AS properties
        ORDER BY source, relationship_type, target
        """,
        database_="neo4j",
    )
    return {
        "nodes": [dict(record) for record in node_records],
        "relationships": [dict(record) for record in relationship_records],
    }


def _canonical_relates_count(driver) -> int:
    records, _, _ = driver.execute_query(
        """
        MATCH (:CanonicalEntity)-[relationship:RELATES]-()
        RETURN count(relationship) AS count
        """,
        database_="neo4j",
    )
    return int(records[0]["count"])


def _snapshot(driver):
    return CanonicalProjectionStore(driver).load_snapshot(
        node_limit=20,
        edge_limit=20,
        evidence_limit=20,
        document_id=None,
        min_confidence=0.5,
    )


def _seed_excluded_and_self_facts(driver, canonical_a: str, canonical_b: str):
    driver.execute_query(
        """
        MATCH (document_a:Document {document_id: 'test_wave3_doc_a'})
              -[:HAS_CHUNK]->(chunk_a:Chunk {chunk_id: 'test_wave3_doc_a#0'})
        MATCH (alpha_a:Entity {entity_id: 'test_wave3_doc_a::alpha'})
        MATCH (beta_a:Entity {entity_id: 'test_wave3_doc_a::beta'})
        MATCH (beta_b:Entity {entity_id: 'test_wave3_doc_b::beta'})
        MATCH (canonical_a:CanonicalEntity {canonical_id: $canonical_a})
        MATCH (canonical_b:CanonicalEntity {canonical_id: $canonical_b})
        MERGE (review:Entity {entity_id: 'test_wave3_doc_a::review'})
          SET review.document_id = 'test_wave3_doc_a',
              review.name = 'Review',
              review.resolution_status = 'review'
        MERGE (unresolved:Entity {entity_id: 'test_wave3_doc_a::unresolved'})
          SET unresolved.document_id = 'test_wave3_doc_a',
              unresolved.name = 'Unresolved',
              unresolved.resolution_status = 'unresolved'
        MERGE (malformed:Entity {entity_id: 'test_wave3_doc_a::malformed'})
          SET malformed.document_id = 'test_wave3_doc_a',
              malformed.name = 'Malformed'
        MERGE (alias:Entity {entity_id: 'test_wave3_doc_a::alpha-alias'})
          SET alias.document_id = 'test_wave3_doc_a',
              alias.name = 'Alpha Alias',
              alias.mention_count = 1
        MERGE (chunk_a)-[:MENTIONS]->(review)
        MERGE (chunk_a)-[:MENTIONS]->(unresolved)
        MERGE (chunk_a)-[:MENTIONS]->(malformed)
        MERGE (chunk_a)-[:MENTIONS]->(alias)
        MERGE (malformed)-[bad_resolution:RESOLVES_TO]->(canonical_a)
          SET bad_resolution.source_document_id = 'test_wave3_doc_a',
              bad_resolution.evidence_chunk_id = 'test_wave3_doc_a#missing'
        MERGE (alias)-[alias_resolution:RESOLVES_TO]->(canonical_a)
          SET alias_resolution.source_document_id = 'test_wave3_doc_a',
              alias_resolution.evidence_chunk_id = 'test_wave3_doc_a#0',
              alias_resolution.method = 'alias',
              alias_resolution.score = 1.0,
              alias_resolution.reason = 'test'
        MERGE (review)-[:RELATES {
          type: '影响', evidence_chunk_id: 'test_wave3_doc_a#0',
          confidence: 0.9
        }]->(beta_a)
        MERGE (unresolved)-[:RELATES {
          type: '依赖', evidence_chunk_id: 'test_wave3_doc_a#0',
          confidence: 0.9
        }]->(beta_a)
        MERGE (malformed)-[:RELATES {
          type: '组成', evidence_chunk_id: 'test_wave3_doc_a#0',
          confidence: 0.9
        }]->(beta_a)
        MERGE (alpha_a)-[:RELATES {
          type: '影响', evidence_chunk_id: 'test_wave3_doc_a#missing',
          confidence: 0.9
        }]->(beta_a)
        MERGE (alpha_a)-[:RELATES {
          type: '约束', evidence_chunk_id: 'test_wave3_doc_a#0',
          confidence: 0.9
        }]->(beta_b)
        MERGE (alpha_a)-[:RELATES {
          type: '对比', evidence_chunk_id: 'test_wave3_doc_a#0',
          confidence: 0.9
        }]->(alias)
        MERGE (single:Chunk {chunk_id: 'test_wave3_doc_a#1'})
          SET single.document_id = 'test_wave3_doc_a'
        MERGE (document_a)-[:HAS_CHUNK]->(single)
        MERGE (single)-[:MENTIONS]->(alpha_a)
        MERGE (alpha_a)-[:RELATES {
          type: '缓解', evidence_chunk_id: 'test_wave3_doc_a#1',
          confidence: 0.9
        }]->(beta_a)
        """,
        canonical_a=canonical_a,
        canonical_b=canonical_b,
        database_="neo4j",
    )


def test_live_cross_document_aggregation_and_api_are_read_only(neo4j_driver):
    canonical_a, _ = _seed_two_document_support(neo4j_driver)
    before = _graph_fingerprint(neo4j_driver)
    assert _canonical_relates_count(neo4j_driver) == 0

    app = create_app()
    app.state.neo4j = neo4j_driver
    app.state.runs = RunStore()
    response = TestClient(app).get(
        "/api/graph/canonical/communities",
        params={"nodeLimit": 20, "edgeLimit": 20, "evidenceLimit": 20},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["coverage"]["projectedSourceRelationCount"] == 2
    assert body["coverage"]["reviewSourceEntityCount"] == 0
    subgraph = TestClient(app).get(
        f"/api/graph/canonical/entities/{canonical_a}/subgraph",
        params={"nodeLimit": 20, "edgeLimit": 20, "evidenceLimit": 20},
    )
    assert subgraph.status_code == 200, subgraph.text
    edge = subgraph.json()["edges"][0]
    assert edge["supportCount"] == edge["evidenceCount"] == 2
    assert [item["documentId"] for item in edge["evidence"]] == [
        "test_wave3_doc_a",
        "test_wave3_doc_b",
    ]
    assert _graph_fingerprint(neo4j_driver) == before
    assert _canonical_relates_count(neo4j_driver) == 0

    document_scope = CanonicalProjectionStore(neo4j_driver).load_snapshot(
        node_limit=20,
        edge_limit=20,
        evidence_limit=20,
        document_id="test_wave3_doc_a",
        min_confidence=0.5,
    )
    assert document_scope.edges[0].support_count == 1
    assert document_scope.edges[0].evidence[0].document_id == "test_wave3_doc_a"
    confidence_scope = CanonicalProjectionStore(neo4j_driver).load_snapshot(
        node_limit=20,
        edge_limit=20,
        evidence_limit=20,
        document_id=None,
        min_confidence=0.8,
    )
    assert confidence_scope.edges[0].support_count == 1
    assert confidence_scope.coverage.source_relation_count == 2
    assert confidence_scope.coverage.projected_source_relation_count == 1
    assert confidence_scope.coverage.excluded_relation_count == 1


def test_live_alias_reassignment_moves_endpoint_without_source_rewrite(
    neo4j_driver,
):
    canonical_a, canonical_b = _seed_two_document_support(neo4j_driver)
    canonical_c = "canonical:test_wave3_alpha_reassigned"
    before = [
        item
        for item in _source_fingerprint(neo4j_driver)
        if item["relationship_type"] == "RELATES"
    ]
    neo4j_driver.execute_query(
        """
        MERGE (replacement:CanonicalEntity {canonical_id: $canonical_c})
          SET replacement.canonical_name = 'Alpha Reassigned',
              replacement.normalized_name = 'alpha reassigned',
              replacement.entity_type = 'Concept',
              replacement.resolution_version = 'v1'
        WITH replacement
        MATCH (source:Entity {entity_id: 'test_wave3_doc_b::alpha-alias'})
        MATCH (source)-[old:RESOLVES_TO]->(:CanonicalEntity)
        DELETE old
        CREATE (source)-[resolution:RESOLVES_TO]->(replacement)
        SET resolution.method = 'alias',
            resolution.score = 1.0,
            resolution.reason = 'test reassignment',
            resolution.source_document_id = source.document_id,
            resolution.evidence_chunk_id = 'test_wave3_doc_b#0'
        """,
        canonical_c=canonical_c,
        database_="neo4j",
    )

    snapshot = _snapshot(neo4j_driver)

    assert {
        (edge.source, edge.target, edge.support_count)
        for edge in snapshot.edges
    } == {
        (canonical_a, canonical_b, 1),
        (canonical_c, canonical_b, 1),
    }
    after = [
        item
        for item in _source_fingerprint(neo4j_driver)
        if item["relationship_type"] == "RELATES"
    ]
    assert after == before
    assert _canonical_relates_count(neo4j_driver) == 0


def test_live_document_deletion_updates_support_without_projection_cleanup(
    neo4j_driver,
):
    _seed_two_document_support(neo4j_driver)
    assert _snapshot(neo4j_driver).edges[0].support_count == 2

    _do_delete(neo4j_driver, "test_wave3_doc_a")
    remaining = _snapshot(neo4j_driver)
    assert len(remaining.edges) == 1
    assert remaining.edges[0].support_count == 1
    assert remaining.edges[0].evidence[0].document_id == "test_wave3_doc_b"

    _do_delete(neo4j_driver, "test_wave3_doc_b")
    final = _snapshot(neo4j_driver)
    assert final.edges == []
    assert final.coverage.source_relation_count == 0
    assert _canonical_relates_count(neo4j_driver) == 0


def test_live_review_malformed_evidence_and_self_facts_are_classified(
    neo4j_driver,
):
    canonical_a, canonical_b = _seed_two_document_support(neo4j_driver)
    _seed_excluded_and_self_facts(neo4j_driver, canonical_a, canonical_b)

    snapshot = _snapshot(neo4j_driver)

    assert len(snapshot.edges) == 1
    assert snapshot.edges[0].source == canonical_a
    assert snapshot.edges[0].target == canonical_b
    assert snapshot.edges[0].type == "使用"
    assert snapshot.edges[0].support_count == 2
    assert snapshot.coverage.model_dump() == {
        "source_entity_count": 8,
        "accepted_source_entity_count": 5,
        "review_source_entity_count": 1,
        "unresolved_source_entity_count": 1,
        "source_relation_count": 9,
        "projected_source_relation_count": 2,
        "excluded_relation_count": 6,
        "collapsed_self_relation_count": 1,
    }
    assert (
        snapshot.coverage.source_relation_count
        == snapshot.coverage.projected_source_relation_count
        + snapshot.coverage.excluded_relation_count
        + snapshot.coverage.collapsed_self_relation_count
    )
    aliases = CanonicalProjectionStore(neo4j_driver).search(
        "Alpha Alias", limit=10, document_id="test_wave3_doc_a"
    )
    assert [node.id for node in aliases] == [canonical_a]
    assert _canonical_relates_count(neo4j_driver) == 0
