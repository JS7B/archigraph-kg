"""Live Neo4j checks for accepted-only, read-only QA relation expansion."""

from __future__ import annotations

import pytest

from app.qa.expand import expand_entities

PREFIX = "test_expand_canonical_"
DOC_A = f"{PREFIX}doc_a"
DOC_B = f"{PREFIX}doc_b"
CANONICAL_A = f"canonical:{PREFIX}alpha"
CANONICAL_B = f"canonical:{PREFIX}beta"


def _delete_scoped_records(driver) -> None:
    driver.execute_query(
        """
        MATCH (node)
        WHERE node.document_id STARTS WITH $prefix
           OR node.canonical_id STARTS WITH $canonical_prefix
        DETACH DELETE node
        """,
        prefix=PREFIX,
        canonical_prefix=f"canonical:{PREFIX}",
        database_="neo4j",
    )


def _scoped_node_count(driver) -> int:
    records, _, _ = driver.execute_query(
        """
        MATCH (node)
        WHERE node.document_id STARTS WITH $prefix
           OR node.canonical_id STARTS WITH $canonical_prefix
        RETURN count(node) AS count
        """,
        prefix=PREFIX,
        canonical_prefix=f"canonical:{PREFIX}",
        database_="neo4j",
    )
    return int(records[0]["count"])


@pytest.fixture(autouse=True)
def _clean_canonical_expand_records(neo4j_driver):
    """Remove canonical nodes that the shared document-only cleanup cannot see."""

    _delete_scoped_records(neo4j_driver)
    assert _scoped_node_count(neo4j_driver) == 0
    yield
    _delete_scoped_records(neo4j_driver)
    assert _scoped_node_count(neo4j_driver) == 0


def _seed(driver) -> list[str]:
    rows = [
        {
            "document_id": DOC_A,
            "chunk_id": f"{DOC_A}#0",
            "source_id": f"{DOC_A}::alpha",
            "target_id": f"{DOC_A}::beta",
        },
        {
            "document_id": DOC_B,
            "chunk_id": f"{DOC_B}#0",
            "source_id": f"{DOC_B}::alpha",
            "target_id": f"{DOC_B}::beta",
        },
    ]
    driver.execute_query(
        """
        MERGE (canonical_a:CanonicalEntity {canonical_id: $canonical_a})
          SET canonical_a.canonical_name = 'Alpha'
        MERGE (canonical_b:CanonicalEntity {canonical_id: $canonical_b})
          SET canonical_b.canonical_name = 'Beta'
        WITH canonical_a, canonical_b
        UNWIND $rows AS row
        MERGE (document:Document {document_id: row.document_id})
        MERGE (chunk:Chunk {chunk_id: row.chunk_id})
          SET chunk.document_id = row.document_id
        MERGE (document)-[:HAS_CHUNK]->(chunk)
        MERGE (source:Entity {entity_id: row.source_id})
          SET source.name = 'Alpha', source.document_id = row.document_id
        MERGE (target:Entity {entity_id: row.target_id})
          SET target.name = 'Beta', target.document_id = row.document_id
        MERGE (chunk)-[:MENTIONS]->(source)
        MERGE (chunk)-[:MENTIONS]->(target)
        MERGE (source)-[source_resolution:RESOLVES_TO]->(canonical_a)
          SET source_resolution.source_document_id = row.document_id,
              source_resolution.evidence_chunk_id = row.chunk_id,
              source_resolution.method = 'exact'
        MERGE (target)-[target_resolution:RESOLVES_TO]->(canonical_b)
          SET target_resolution.source_document_id = row.document_id,
              target_resolution.evidence_chunk_id = row.chunk_id,
              target_resolution.method = 'exact'
        MERGE (source)-[relation:RELATES {
          type: 'uses', evidence_chunk_id: row.chunk_id
        }]->(target)
          SET relation.confidence = 0.9
        """,
        rows=rows,
        canonical_a=CANONICAL_A,
        canonical_b=CANONICAL_B,
        database_="neo4j",
    )
    _seed_excluded_facts(driver)
    return [row["chunk_id"] for row in rows]


def _seed_excluded_facts(driver) -> None:
    driver.execute_query(
        """
        MATCH (document:Document {document_id: $doc})
              -[:HAS_CHUNK]->(chunk:Chunk {chunk_id: $chunk_id})
        MATCH (source:Entity {entity_id: $source_id})
        MATCH (target:Entity {entity_id: $target_id})
        MATCH (cross_target:Entity {entity_id: $cross_target_id})
        MATCH (canonical_a:CanonicalEntity {canonical_id: $canonical_a})
        MATCH (canonical_b:CanonicalEntity {canonical_id: $canonical_b})
        MERGE (review:Entity {entity_id: $review_id})
          SET review.name = 'Review', review.document_id = $doc,
              review.resolution_status = 'review'
        MERGE (unresolved:Entity {entity_id: $unresolved_id})
          SET unresolved.name = 'Unresolved', unresolved.document_id = $doc,
              unresolved.resolution_status = 'unresolved'
        MERGE (bad_resolution:Entity {entity_id: $bad_resolution_id})
          SET bad_resolution.name = 'Bad Resolution',
              bad_resolution.document_id = $doc
        MERGE (alias:Entity {entity_id: $alias_id})
          SET alias.name = 'Alpha Alias', alias.document_id = $doc
        MERGE (chunk)-[:MENTIONS]->(review)
        MERGE (chunk)-[:MENTIONS]->(unresolved)
        MERGE (chunk)-[:MENTIONS]->(bad_resolution)
        MERGE (chunk)-[:MENTIONS]->(alias)
        MERGE (chunk)-[:MENTIONS]->(cross_target)
        MERGE (review)-[review_resolution:RESOLVES_TO]->(canonical_a)
          SET review_resolution.source_document_id = $doc,
              review_resolution.evidence_chunk_id = $chunk_id
        MERGE (unresolved)-[unresolved_resolution:RESOLVES_TO]->(canonical_b)
          SET unresolved_resolution.source_document_id = $doc,
              unresolved_resolution.evidence_chunk_id = $chunk_id
        MERGE (bad_resolution)-[bad_link:RESOLVES_TO]->(canonical_a)
          SET bad_link.source_document_id = $doc,
              bad_link.evidence_chunk_id = $missing_chunk_id
        MERGE (alias)-[alias_resolution:RESOLVES_TO]->(canonical_a)
          SET alias_resolution.source_document_id = $doc,
              alias_resolution.evidence_chunk_id = $chunk_id
        MERGE (review)-[:RELATES {
          type: 'review_fact', evidence_chunk_id: $chunk_id
        }]->(target)
        MERGE (source)-[:RELATES {
          type: 'unresolved_fact', evidence_chunk_id: $chunk_id
        }]->(unresolved)
        MERGE (bad_resolution)-[:RELATES {
          type: 'bad_resolution_fact', evidence_chunk_id: $chunk_id
        }]->(target)
        MERGE (source)-[:RELATES {
          type: 'fake_relation_evidence', evidence_chunk_id: $missing_chunk_id
        }]->(target)
        MERGE (source)-[:RELATES {
          type: 'cross_document', evidence_chunk_id: $chunk_id
        }]->(cross_target)
        MERGE (source)-[:RELATES {
          type: 'canonical_self', evidence_chunk_id: $chunk_id
        }]->(alias)
        MERGE (single:Chunk {chunk_id: $single_chunk_id})
          SET single.document_id = $doc
        MERGE (document)-[:HAS_CHUNK]->(single)
        MERGE (single)-[:MENTIONS]->(source)
        MERGE (source)-[:RELATES {
          type: 'single_endpoint_mention', evidence_chunk_id: $single_chunk_id
        }]->(target)
        """,
        doc=DOC_A,
        chunk_id=f"{DOC_A}#0",
        single_chunk_id=f"{DOC_A}#1",
        missing_chunk_id=f"{DOC_A}#missing",
        source_id=f"{DOC_A}::alpha",
        target_id=f"{DOC_A}::beta",
        cross_target_id=f"{DOC_B}::beta",
        review_id=f"{DOC_A}::review",
        unresolved_id=f"{DOC_A}::unresolved",
        bad_resolution_id=f"{DOC_A}::bad-resolution",
        alias_id=f"{DOC_A}::alpha-alias",
        canonical_a=CANONICAL_A,
        canonical_b=CANONICAL_B,
        database_="neo4j",
    )


def _fingerprint(driver) -> dict[str, list[dict]]:
    nodes, _, _ = driver.execute_query(
        """
        MATCH (node)
        WHERE node.document_id STARTS WITH $prefix
           OR node.canonical_id STARTS WITH $canonical_prefix
        RETURN labels(node) AS labels,
               coalesce(node.entity_id, node.chunk_id,
                        node.canonical_id, node.document_id) AS identity,
               properties(node) AS properties
        ORDER BY identity, labels
        """,
        prefix=PREFIX,
        canonical_prefix=f"canonical:{PREFIX}",
        database_="neo4j",
    )
    relationships, _, _ = driver.execute_query(
        """
        MATCH (source)-[relationship]->(target)
        WHERE source.document_id STARTS WITH $prefix
           OR source.canonical_id STARTS WITH $canonical_prefix
           OR target.document_id STARTS WITH $prefix
           OR target.canonical_id STARTS WITH $canonical_prefix
        RETURN coalesce(source.entity_id, source.chunk_id,
                        source.canonical_id, source.document_id) AS source,
               type(relationship) AS relationship_type,
               coalesce(target.entity_id, target.chunk_id,
                        target.canonical_id, target.document_id) AS target,
               properties(relationship) AS properties
        ORDER BY source, relationship_type, target
        """,
        prefix=PREFIX,
        canonical_prefix=f"canonical:{PREFIX}",
        database_="neo4j",
    )
    return {
        "nodes": [dict(record) for record in nodes],
        "relationships": [dict(record) for record in relationships],
    }


def _canonical_relates_count(driver) -> int:
    records, _, _ = driver.execute_query(
        """
        MATCH (canonical:CanonicalEntity)-[relationship:RELATES]-()
        WHERE canonical.canonical_id STARTS WITH $canonical_prefix
        RETURN count(relationship) AS count
        """,
        canonical_prefix=f"canonical:{PREFIX}",
        database_="neo4j",
    )
    return int(records[0]["count"])


def test_expand_returns_only_accepted_aggregated_paths_without_writes(ensured_schema):
    chunk_ids = _seed(ensured_schema)
    before = _fingerprint(ensured_schema)
    assert _canonical_relates_count(ensured_schema) == 0

    # One evidence-pool Chunk seeds the canonical identity; all eligible source
    # facts for that canonical source are then aggregated across documents.
    context = expand_entities(ensured_schema, chunk_ids[:1])

    assert len(context.paths) == 1
    path = context.paths[0]
    assert path.source_canonical_id == CANONICAL_A
    assert path.target_canonical_id == CANONICAL_B
    assert path.source_name == "Alpha"
    assert path.target_name == "Beta"
    assert path.type == "uses"
    assert path.support_count == 2
    assert [item.document_id for item in path.provenance] == [DOC_A, DOC_B]
    assert _fingerprint(ensured_schema) == before
    assert _canonical_relates_count(ensured_schema) == 0


def test_empty_chunk_ids_returns_empty_without_query(ensured_schema):
    assert expand_entities(ensured_schema, []).paths == []
