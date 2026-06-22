"""实体邻域扩展：从召回的 chunk 出发，沿 MENTIONS 找实体、RELATES 扩 1 跳。

手写 Cypher，编排控制权留在项目内。产出去重的 RelationPath 列表，
每条带 evidence_chunk_id，保证关系也能回溯到来源 chunk。
"""

import logging

from neo4j import Driver

from app.qa.models import RelationPath, RetrievalContext

logger = logging.getLogger(__name__)

_EXPAND = """
UNWIND $chunk_ids AS cid
MATCH (c:Chunk {chunk_id: cid})-[:MENTIONS]->(e:Entity)
MATCH (e)-[r:RELATES]->(nbr:Entity)
RETURN DISTINCT e.name AS source_name, nbr.name AS target_name,
       r.type AS type, r.evidence_chunk_id AS evidence_chunk_id
"""


def expand_entities(
    driver: Driver, chunk_ids: list[str], *, database: str = "neo4j"
) -> RetrievalContext:
    """从 chunk 提及的实体出发扩 1 跳关系，返回去重的关系路径集。"""
    if not chunk_ids:
        return RetrievalContext(paths=[])
    records, _, _ = driver.execute_query(
        _EXPAND, chunk_ids=chunk_ids, database_=database
    )
    paths = [
        RelationPath(
            source_name=r["source_name"],
            target_name=r["target_name"],
            type=r["type"],
            evidence_chunk_id=r["evidence_chunk_id"],
        )
        for r in records
    ]
    return RetrievalContext(paths=paths)
