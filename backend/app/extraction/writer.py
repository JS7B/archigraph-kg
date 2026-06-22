"""把合并后的实体与关系写入 Neo4j：Entity / MENTIONS / RELATES。

幂等：Entity 按 entity_id MERGE；MENTIONS/RELATES 用 MERGE。Chunk 用 MATCH（不 MERGE），
依赖上一板块 ingest_document 已写入，避免凭空造孤立 Chunk。Entity 必带 document_id，
否则测试清理（document_id STARTS WITH 'test_'）会漏删，污染共享库。
"""

from neo4j import Driver

from app.extraction.models import DocumentExtraction

_MERGE_ENTITIES = """
UNWIND $entities AS e
  MERGE (n:Entity {entity_id: e.entity_id})
    SET n.name = e.name,
        n.entity_type = e.type,
        n.normalized_name = e.normalized_name,
        n.description = e.description,
        n.document_id = $document_id
"""

_MERGE_MENTIONS = """
UNWIND $mentions AS m
  MATCH (c:Chunk {chunk_id: m.chunk_id})
  MATCH (e:Entity {entity_id: m.entity_id})
  MERGE (c)-[:MENTIONS]->(e)
"""

_MERGE_RELATIONS = """
UNWIND $relations AS r
  MATCH (s:Entity {entity_id: r.source_id})
  MATCH (t:Entity {entity_id: r.target_id})
  MERGE (s)-[rel:RELATES {type: r.type, evidence_chunk_id: r.evidence_chunk_id}]->(t)
    SET rel.confidence = r.confidence
"""


def write_extraction(
    driver: Driver,
    document_id: str,
    extraction: DocumentExtraction,
    *,
    database: str = "neo4j",
) -> tuple[int, int, int]:
    """写入实体/Mention/关系，返回 (实体数, 关系数, mention 数)。"""
    entities = [e.model_dump() for e in extraction.entities]
    mentions = [
        {"chunk_id": cid, "entity_id": e.entity_id}
        for e in extraction.entities
        for cid in e.mention_chunk_ids
    ]
    relations = [r.model_dump() for r in extraction.relations]

    driver.execute_query(
        _MERGE_ENTITIES, entities=entities, document_id=document_id, database_=database
    )
    driver.execute_query(_MERGE_MENTIONS, mentions=mentions, database_=database)
    driver.execute_query(_MERGE_RELATIONS, relations=relations, database_=database)
    return len(entities), len(relations), len(mentions)
