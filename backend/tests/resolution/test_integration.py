from app.graph.schema import ensure_schema
from app.resolution.backfill import backfill_canonical_overlay
from app.resolution.identity import canonical_id_for_name
from app.resolution.models import AliasRecord, ResolutionMethod, SourceEntityRecord
from app.resolution.persistence import CanonicalOverlayStore
from app.resolution.service import resolve_source_entities
from app.runs.tasks import _do_delete


def _seed_source(driver, document_id, chunk_id, entity_id, name):
    driver.execute_query(
        """
        MERGE (d:Document {document_id: $document_id})
        MERGE (c:Chunk {chunk_id: $chunk_id})
          SET c.document_id = $document_id
        MERGE (d)-[:HAS_CHUNK]->(c)
        MERGE (e:Entity {entity_id: $entity_id})
          SET e.document_id = $document_id,
              e.name = $name,
              e.normalized_name = $normalized_name,
              e.entity_type = 'test_type'
        MERGE (c)-[:MENTIONS]->(e)
        """,
        document_id=document_id,
        chunk_id=chunk_id,
        entity_id=entity_id,
        name=name,
        normalized_name=name.casefold(),
        database_="neo4j",
    )


def test_real_neo4j_backfill_idempotence_and_delete_lifecycle(resolution_neo4j_driver):
    driver = resolution_neo4j_driver
    ensure_schema(driver)
    shared_name = "test_resolution_shared_concept"
    for document_id, chunk_id, entity_id, name in (
        (
            "test_resolution_a",
            "test_resolution_a#0",
            "test_resolution_a::shared",
            shared_name,
        ),
        (
            "test_resolution_b",
            "test_resolution_b#0",
            "test_resolution_b::shared",
            shared_name.upper(),
        ),
    ):
        _seed_source(driver, document_id, chunk_id, entity_id, name)
    driver.execute_query(
        """
        MATCH (a:Entity {entity_id: 'test_resolution_a::shared'})
        MATCH (b:Entity {entity_id: 'test_resolution_b::shared'})
        MERGE (a)-[:RELATES {type: 'mentions', evidence_chunk_id: 'test_resolution_a#0'}]->(b)
        """,
        database_="neo4j",
    )

    first = backfill_canonical_overlay(driver)
    second = backfill_canonical_overlay(driver)

    assert first.accepted_count == second.accepted_count == 2
    canonical_id = canonical_id_for_name(shared_name)
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


def test_real_delete_cleans_residual_entity_when_document_is_already_missing(
    resolution_neo4j_driver,
):
    driver = resolution_neo4j_driver
    ensure_schema(driver)
    document_id = "test_resolution_residual"
    chunk_id = "test_resolution_residual#0"
    entity_id = "test_resolution_residual::entity"
    name = "test_resolution_residual_concept"
    _seed_source(driver, document_id, chunk_id, entity_id, name)
    source = SourceEntityRecord(
        entity_id=entity_id,
        name=name,
        entity_type="test_type",
        normalized_name=name,
        document_id=document_id,
        mention_chunk_ids=[chunk_id],
    )
    result = resolve_source_entities(driver, [source])
    canonical_id = result.decisions[0].canonical_id
    driver.execute_query(
        """
        MATCH (d:Document {document_id: $document_id})
        OPTIONAL MATCH (d)-[:HAS_CHUNK]->(c:Chunk)
        DETACH DELETE c
        DETACH DELETE d
        """,
        document_id=document_id,
        database_="neo4j",
    )

    _do_delete(driver, document_id)

    records, _, _ = driver.execute_query(
        """
        OPTIONAL MATCH (e:Entity {entity_id: $entity_id})
        OPTIONAL MATCH (c:CanonicalEntity {canonical_id: $canonical_id})
        RETURN count(DISTINCT e) AS entities, count(DISTINCT c) AS canonicals
        """,
        entity_id=entity_id,
        canonical_id=canonical_id,
        database_="neo4j",
    )
    assert dict(records[0]) == {"entities": 0, "canonicals": 0}


def test_real_alias_is_reconstructed_then_disappears_with_its_source(
    resolution_neo4j_driver,
):
    driver = resolution_neo4j_driver
    ensure_schema(driver)
    target_document_id = "test_resolution_alias_target_doc"
    target_chunk_id = "test_resolution_alias_target_doc#0"
    target_entity_id = "test_resolution_alias_target_doc::target"
    target_name = "test_resolution_alias_target"
    alias_document_id = "test_resolution_alias_source_doc"
    alias_chunk_id = "test_resolution_alias_source_doc#0"
    alias_entity_id = "test_resolution_alias_source_doc::alias"
    alias_name = "test_resolution_alias_spelling"
    _seed_source(
        driver,
        target_document_id,
        target_chunk_id,
        target_entity_id,
        target_name,
    )
    _seed_source(
        driver,
        alias_document_id,
        alias_chunk_id,
        alias_entity_id,
        alias_name,
    )
    target = SourceEntityRecord(
        entity_id=target_entity_id,
        name=target_name,
        entity_type="test_type",
        normalized_name=target_name,
        document_id=target_document_id,
        mention_chunk_ids=[target_chunk_id],
    )
    alias_source = SourceEntityRecord(
        entity_id=alias_entity_id,
        name=alias_name,
        entity_type="test_type",
        normalized_name=alias_name,
        document_id=alias_document_id,
        mention_chunk_ids=[alias_chunk_id],
    )
    # Simulate legacy/previously separated identities before an explicit
    # provenance-carrying alias correction is supplied.
    initial = resolve_source_entities(
        driver, [target, alias_source], fuzzy_threshold=1.0
    )
    target_canonical_id = next(
        decision.canonical_id
        for decision in initial.decisions
        if decision.source_entity_id == target_entity_id
    )
    old_alias_canonical_id = next(
        decision.canonical_id
        for decision in initial.decisions
        if decision.source_entity_id == alias_entity_id
    )
    alias = AliasRecord(
        alias=alias_name,
        canonical_id=target_canonical_id,
        source_entity_id=alias_entity_id,
        source_document_id=alias_document_id,
        source_chunk_id=alias_chunk_id,
    )

    first = resolve_source_entities(driver, [alias_source], aliases=[alias])
    second = resolve_source_entities(driver, [alias_source])

    assert first.decisions[0].method is ResolutionMethod.ALIAS
    assert first.decisions[0].canonical_id == target_canonical_id
    assert second.decisions[0].method is ResolutionMethod.ALIAS
    assert second.decisions[0].canonical_id == target_canonical_id
    reconstructed = CanonicalOverlayStore(driver).load_reconstructed_aliases()
    assert alias in reconstructed
    edges, _, _ = driver.execute_query(
        """
        MATCH (source:Entity {entity_id: $entity_id})
        OPTIONAL MATCH (source)-[resolution:RESOLVES_TO]->(target:CanonicalEntity)
        OPTIONAL MATCH (old:CanonicalEntity {canonical_id: $old_canonical_id})
        RETURN count(DISTINCT resolution) AS links,
               collect(DISTINCT target.canonical_id) AS target_ids,
               count(DISTINCT old) AS old_canonicals
        """,
        entity_id=alias_entity_id,
        old_canonical_id=old_alias_canonical_id,
        database_="neo4j",
    )
    assert edges[0]["links"] == 1
    assert edges[0]["target_ids"] == [target_canonical_id]
    assert edges[0]["old_canonicals"] == 0

    _do_delete(driver, alias_document_id)

    reconstructed_after_delete = (
        CanonicalOverlayStore(driver).load_reconstructed_aliases()
    )
    assert alias not in reconstructed_after_delete
    kept, _, _ = driver.execute_query(
        """
        MATCH (canonical:CanonicalEntity {canonical_id: $canonical_id})
        RETURN count(canonical) AS count
        """,
        canonical_id=target_canonical_id,
        database_="neo4j",
    )
    assert kept[0]["count"] == 1
