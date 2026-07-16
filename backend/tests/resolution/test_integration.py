from app.graph.schema import ensure_schema
from app.resolution.backfill import backfill_canonical_overlay
from app.resolution.identity import canonical_id_for_name
from app.runs.tasks import _do_delete


def test_real_neo4j_backfill_idempotence_and_delete_lifecycle(resolution_neo4j_driver):
    driver = resolution_neo4j_driver
    ensure_schema(driver)
    for document_id, chunk_id, entity_id, name in (
        ("test_resolution_a", "test_resolution_a#0", "test_resolution_a::neo4j", "Neo4j"),
        ("test_resolution_b", "test_resolution_b#0", "test_resolution_b::neo4j", "neo4j"),
    ):
        driver.execute_query(
            """
            MERGE (d:Document {document_id: $document_id})
            MERGE (c:Chunk {chunk_id: $chunk_id})
              SET c.document_id = $document_id
            MERGE (d)-[:HAS_CHUNK]->(c)
            MERGE (e:Entity {entity_id: $entity_id})
              SET e.document_id = $document_id,
                  e.name = $name,
                  e.normalized_name = 'neo4j',
                  e.entity_type = 'database'
            MERGE (c)-[:MENTIONS]->(e)
            """,
            document_id=document_id,
            chunk_id=chunk_id,
            entity_id=entity_id,
            name=name,
            database_="neo4j",
        )
    driver.execute_query(
        """
        MATCH (a:Entity {entity_id: 'test_resolution_a::neo4j'})
        MATCH (b:Entity {entity_id: 'test_resolution_b::neo4j'})
        MERGE (a)-[:RELATES {type: 'mentions', evidence_chunk_id: 'test_resolution_a#0'}]->(b)
        """,
        database_="neo4j",
    )

    first = backfill_canonical_overlay(driver)
    second = backfill_canonical_overlay(driver)

    assert first.accepted_count == second.accepted_count == 2
    canonical_id = canonical_id_for_name("Neo4j")
    records, _, _ = driver.execute_query(
        """
        MATCH (canonical:CanonicalEntity {canonical_id: $canonical_id})
        OPTIONAL MATCH (:Entity)-[resolution:RESOLVES_TO]->(canonical)
        RETURN count(DISTINCT canonical) AS canonicals,
               count(resolution) AS links,
               canonical:Entity AS has_entity_label
        """,
        canonical_id=canonical_id,
        database_="neo4j",
    )
    assert dict(records[0]) == {
        "canonicals": 1,
        "links": 2,
        "has_entity_label": False,
    }
    source_counts, _, _ = driver.execute_query(
        """
        MATCH (e:Entity) WHERE e.document_id STARTS WITH 'test_resolution_'
        OPTIONAL MATCH (c:Chunk)-[m:MENTIONS]->(e)
        OPTIONAL MATCH (e)-[r:RELATES]->()
        RETURN count(DISTINCT e) AS entities,
               count(DISTINCT m) AS mentions,
               count(DISTINCT r) AS relations
        """,
        database_="neo4j",
    )
    assert dict(source_counts[0]) == {"entities": 2, "mentions": 2, "relations": 1}

    _do_delete(driver, "test_resolution_a")
    kept, _, _ = driver.execute_query(
        "MATCH (c:CanonicalEntity {canonical_id: $canonical_id}) "
        "RETURN count(c) AS count",
        canonical_id=canonical_id,
        database_="neo4j",
    )
    assert kept[0]["count"] == 1

    _do_delete(driver, "test_resolution_b")
    removed, _, _ = driver.execute_query(
        "MATCH (c:CanonicalEntity {canonical_id: $canonical_id}) "
        "RETURN count(c) AS count",
        canonical_id=canonical_id,
        database_="neo4j",
    )
    assert removed[0]["count"] == 0
