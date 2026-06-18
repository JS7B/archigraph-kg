"""向量查询：用 chunk 向量索引召回 top-k 相似 chunk，带回来源位置与相似度。

用 Neo4j 原生 db.index.vector.queryNodes（cosine）。score 越大越相似，过程已按降序返回。
回读的 ChunkHit 携带完整 provenance，供上层组装引用。
"""

from neo4j import Driver
from pydantic import BaseModel, Field

from app.graph.schema import CHUNK_VECTOR_INDEX

_SEARCH = f"""
CALL db.index.vector.queryNodes('{CHUNK_VECTOR_INDEX}', $top_k, $query_embedding)
YIELD node AS c, score
MATCH (d:Document)-[:HAS_CHUNK]->(c)
RETURN c.chunk_id AS chunk_id, c.document_id AS document_id,
       c.chunk_index AS chunk_index, c.text AS text,
       c.char_start AS char_start, c.char_end AS char_end,
       c.page AS page, c.heading_path AS heading_path, score
ORDER BY score DESC
"""


class ChunkHit(BaseModel):
    """一条向量召回结果：chunk 内容 + 来源位置 + 相似度。"""

    chunk_id: str
    document_id: str
    chunk_index: int
    text: str
    char_start: int
    char_end: int
    page: int | None = None
    heading_path: list[str] = Field(default_factory=list)
    score: float


def search_chunks(
    driver: Driver,
    query_embedding: list[float],
    *,
    top_k: int = 5,
    database: str = "neo4j",
) -> list[ChunkHit]:
    """按查询向量召回 top-k 相似 chunk，按相似度降序返回。"""
    records, _, _ = driver.execute_query(
        _SEARCH,
        top_k=top_k,
        query_embedding=query_embedding,
        database_=database,
    )
    return [ChunkHit(**record.data()) for record in records]
