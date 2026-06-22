"""问答 API 集成（真实 LLM gate）：端到端 POST /api/chat + GET /api/chunks/{id}。

向量召回本身已由 graph 板块 test_search 覆盖；这里 monkeypatch search_chunks 直接返回
已写入的 chunk（避开真实 3072 维与测试 8 维索引的冲突），让真实 rerank + 真实 chat 跑通，
重点验证：路由、reranker、邻域扩展、上下文组装、LLM 带引用答案、chunk 反查。
"""

import pytest
from fastapi.testclient import TestClient

from app.clients.llm import is_configured
from app.graph.search import ChunkHit
from app.main import create_app
from app.qa import pipeline as pipeline_mod

pytestmark = pytest.mark.skipif(
    not is_configured(), reason="LLM 未配置，跳过问答 API 真实测试"
)

DOC = "test_qa_doc"


def _seed_graph(driver):
    """写入 2 个 chunk + 实体 + 关系（8 维占位向量，匹配测试索引）。"""
    driver.execute_query(
        """
        MERGE (d:Document {document_id: $doc}) SET d.source_path = 'qa/doc.md'
        MERGE (c0:Chunk {chunk_id: $c0})
          SET c0.document_id=$doc, c0.text=$t0, c0.chunk_index=0,
              c0.char_start=0, c0.char_end=40, c0.heading_path=['GraphRAG 系统'],
              c0.embedding=$vec
        MERGE (c1:Chunk {chunk_id: $c1})
          SET c1.document_id=$doc, c1.text=$t1, c1.chunk_index=1,
              c1.char_start=40, c1.char_end=80, c1.heading_path=['GraphRAG 系统'],
              c1.embedding=$vec
        MERGE (d)-[:HAS_CHUNK]->(c0)
        MERGE (d)-[:HAS_CHUNK]->(c1)
        MERGE (e1:Entity {entity_id: $e1}) SET e1.name='GraphRAG', e1.document_id=$doc
        MERGE (e2:Entity {entity_id: $e2}) SET e2.name='Neo4j', e2.document_id=$doc
        MERGE (c0)-[:MENTIONS]->(e1)
        MERGE (c0)-[:MENTIONS]->(e2)
        MERGE (e1)-[:RELATES {type:'依赖', evidence_chunk_id:$c0}]->(e2)
        """,
        doc=DOC, c0=f"{DOC}#0", c1=f"{DOC}#1",
        t0="GraphRAG 依赖 Neo4j 存储知识图谱，使用向量检索召回相关片段。",
        t1="FastAPI 提供后端接口，Pydantic 负责数据校验。",
        vec=[0.1] * 8, e1=f"{DOC}::graphrag::技术概念", e2=f"{DOC}::neo4j::产品模块",
        database_="neo4j",
    )


def _hits():
    return [
        ChunkHit(
            chunk_id=f"{DOC}#0", document_id=DOC, chunk_index=0,
            text="GraphRAG 依赖 Neo4j 存储知识图谱，使用向量检索召回相关片段。",
            char_start=0, char_end=40, heading_path=["GraphRAG 系统"], score=0.9,
        ),
        ChunkHit(
            chunk_id=f"{DOC}#1", document_id=DOC, chunk_index=1,
            text="FastAPI 提供后端接口，Pydantic 负责数据校验。",
            char_start=40, char_end=80, heading_path=["GraphRAG 系统"], score=0.8,
        ),
    ]


def _client(driver):
    """构造 TestClient 并注入测试 driver（不走 lifespan，避免重连/重建 schema）。"""
    app = create_app()
    app.state.neo4j = driver
    return TestClient(app)


def test_chat_returns_answer_with_citations(ensured_schema, monkeypatch):
    _seed_graph(ensured_schema)
    monkeypatch.setattr(
        pipeline_mod, "search_chunks", lambda d, v, *, top_k, database: _hits()
    )
    client = _client(ensured_schema)
    resp = client.post("/api/chat", json={"question": "GraphRAG 依赖什么来存储知识图谱？"})
    assert resp.status_code == 200
    body = resp.json()
    assert "text" in body and body["text"]
    assert "confidence" in body
    # 答案应带引用，且 citation 字段是 camelCase
    if body["citations"]:
        c = body["citations"][0]
        assert "chunkId" in c and "documentId" in c and "index" in c
        assert c["chunkId"].startswith(DOC)


def test_get_chunk_returns_text(ensured_schema):
    _seed_graph(ensured_schema)
    client = _client(ensured_schema)
    resp = client.get(f"/api/chunks/{DOC}%230")  # %23 = '#'
    assert resp.status_code == 200
    body = resp.json()
    assert body["chunkId"] == f"{DOC}#0"
    assert body["documentName"] == "qa/doc.md"
    assert "Neo4j" in body["text"]
    assert "GraphRAG 系统" in body["location"]


def test_get_missing_chunk_404(ensured_schema):
    client = _client(ensured_schema)
    resp = client.get("/api/chunks/test_qa_doc%23999")
    assert resp.status_code == 404
