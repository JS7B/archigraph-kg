"""图谱 schema：唯一约束与 chunk 向量索引的幂等创建。

约束/索引均用 IF NOT EXISTS，可重复调用无副作用。向量索引创建后异步构建，
须 awaitIndexes 等其 ONLINE，否则首次查询会抛 51N63（索引仍在 POPULATING）。
"""

import logging

from neo4j import Driver

from app.config import get_settings

logger = logging.getLogger(__name__)

CHUNK_VECTOR_INDEX = "chunk_embedding"
# 会话消息向量索引（多轮对话记忆）：与 chunk 索引不同 label，可独立共存。
MESSAGE_VECTOR_INDEX = "message_embedding"

_CONSTRAINTS = (
    "CREATE CONSTRAINT document_id_unique IF NOT EXISTS "
    "FOR (d:Document) REQUIRE d.document_id IS UNIQUE",
    "CREATE CONSTRAINT chunk_id_unique IF NOT EXISTS "
    "FOR (c:Chunk) REQUIRE c.chunk_id IS UNIQUE",
    "CREATE CONSTRAINT entity_id_unique IF NOT EXISTS "
    "FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE",
    "CREATE CONSTRAINT canonical_entity_id_unique IF NOT EXISTS "
    "FOR (c:CanonicalEntity) REQUIRE c.canonical_id IS UNIQUE",
    "CREATE INDEX canonical_entity_normalized_name IF NOT EXISTS "
    "FOR (c:CanonicalEntity) ON (c.normalized_name)",
    "CREATE CONSTRAINT conversation_id_unique IF NOT EXISTS "
    "FOR (cv:Conversation) REQUIRE cv.conversation_id IS UNIQUE",
    "CREATE CONSTRAINT message_id_unique IF NOT EXISTS "
    "FOR (m:Message) REQUIRE m.message_id IS UNIQUE",
)


def ensure_schema(
    driver: Driver,
    *,
    dim: int | None = None,
    index_name: str = CHUNK_VECTOR_INDEX,
    database: str = "neo4j",
) -> None:
    """创建唯一约束与 chunk 向量索引，并等待索引上线。

    dim 缺省取配置 embedding_dim；它决定向量索引维度，须与 embedding 模型实际输出一致。
    indexConfig 不接受 Cypher 参数，维度只能插值进 DDL —— dim 是可信 int 配置，插值安全。
    index_name 默认生产索引名；测试传独立名（chunk_embedding_test）实现物理隔离，
    根治 L6：测试索引与生产分离，即使 teardown 不执行也不污染生产索引。
    """
    if dim is None:
        dim = get_settings().embedding_dim

    for cypher in _CONSTRAINTS:
        driver.execute_query(cypher, database_=database)

    driver.execute_query(
        f"CREATE VECTOR INDEX {index_name} IF NOT EXISTS "
        "FOR (c:Chunk) ON (c.embedding) "
        "OPTIONS { indexConfig: { "
        f"`vector.dimensions`: {dim}, "
        "`vector.similarity_function`: 'cosine' } }",
        database_=database,
    )
    # 会话消息向量索引（多轮对话记忆）：label 是 Message，与 chunk 索引独立共存。
    driver.execute_query(
        f"CREATE VECTOR INDEX {MESSAGE_VECTOR_INDEX} IF NOT EXISTS "
        "FOR (m:Message) ON (m.embedding) "
        "OPTIONS { indexConfig: { "
        f"`vector.dimensions`: {dim}, "
        "`vector.similarity_function`: 'cosine' } }",
        database_=database,
    )
    driver.execute_query("CALL db.awaitIndexes(120)", database_=database)
    logger.info(
        "Neo4j schema ready: constraints + vector indexes %s/%s (dim=%d)",
        index_name, MESSAGE_VECTOR_INDEX, dim,
    )
