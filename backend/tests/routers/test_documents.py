"""文档库路由测试（A 板块）。

POST /api/documents 同步跑 parse→写图（真实），embedding 与抽取用 monkeypatch
避开真实 LLM（保持测试快速 + 维度兼容测试索引 8 维）。重点验证：
路由契约、camelCase、幂等、400/413、chunk 反查、临时文件清理、状态字段。
"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.extraction.models import ExtractionStats
from app.main import create_app
from app.routers import documents as docs_mod

TEST_DIM = 8


def _fake_embeddings(doc):
    """产与 chunk 同序的 TEST_DIM 维占位向量（绕开真实 embedding，匹配测试索引）。"""
    return [[0.1] * TEST_DIM for _ in doc.chunks]


def _fake_stats(driver, doc, *, max_attempts=3, database="neo4j"):
    """假抽取统计（绕开真实 LLM 抽取）。签名对齐 extract_and_ingest。"""
    return ExtractionStats(
        document_id=doc.document_id,
        entity_count=3,
        relation_count=2,
        mention_count=3,
        failed_chunks=[],
    )


def _client(driver):
    """构造 TestClient 并注入测试 driver（不走 lifespan）。"""
    app = create_app()
    app.state.neo4j = driver
    return TestClient(app)


def _upload(client, name: str, content: bytes):
    """上传文件，返回 response。"""
    return client.post(
        "/api/documents",
        files={"file": (name, content, "application/octet-stream")},
    )


@pytest.fixture(autouse=True)
def _patch_llm(monkeypatch):
    """全局 mock embedding + 抽取，避免真实 LLM 调用；并把 embedding 维度对齐测试索引。

    测试向量索引是 TEST_DIM=8（见 conftest），生产是 3072。ingest_document 缺省读配置
    embedding_dim 做维度校验，这里把配置实例的 embedding_dim 临时设成 8，让 8 维占位
    向量通过校验并真正写入图库（写图逻辑本身仍走真实代码，不被 mock）。
    """
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "embedding_dim", TEST_DIM)
    monkeypatch.setattr(docs_mod, "embed_chunks", _fake_embeddings)
    monkeypatch.setattr(docs_mod, "extract_and_ingest", _fake_stats)

# ── 成功上传：md/txt/pdf ──

def test_upload_markdown(ensured_schema, tmp_path):
    client = _client(ensured_schema)
    content = b"# Test Doc\n\nGraphRAG uses Neo4j to store knowledge graph.\n"
    resp = _upload(client, "test_md_doc.md", content)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["documentId"] == "test_md_doc.md"
    assert body["documentName"] == "test_md_doc.md"
    assert body["chunkCount"] >= 1
    assert body["extraction"]["entityCount"] == 3
    assert body["extraction"]["failedChunks"] == 0


def test_upload_txt(ensured_schema):
    client = _client(ensured_schema)
    content = "FastAPI provides backend APIs. Pydantic validates data.\n".encode()
    resp = _upload(client, "test_txt_doc.txt", content)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["documentId"] == "test_txt_doc.txt"
    assert body["chunkCount"] >= 1


def test_upload_pdf(ensured_schema):
    """PDF 用 samples/evals 下的小 fixture；没有则跳过。"""
    pdfs = list(Path("samples").glob("*.pdf")) + list(Path("evals").glob("*.pdf"))
    if not pdfs:
        pytest.skip("无 PDF 样本，跳过 PDF 上传测试")
    client = _client(ensured_schema)
    pdf_path = pdfs[0]
    resp = _upload(client, "test_pdf_doc.pdf", pdf_path.read_bytes())
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["documentId"] == "test_pdf_doc.pdf"
    assert body["chunkCount"] >= 1


# ── 幂等：重复上传不翻倍（硬要求）──

def test_upload_idempotent(ensured_schema):
    client = _client(ensured_schema)
    content = b"# Idempotent\n\nSame content uploaded twice.\n"
    r1 = _upload(client, "test_idem.md", content)
    assert r1.status_code == 200
    count1 = r1.json()["chunkCount"]
    r2 = _upload(client, "test_idem.md", content)
    assert r2.status_code == 200
    count2 = r2.json()["chunkCount"]
    assert count1 == count2, f"重复上传 chunk 数翻倍: {count1} -> {count2}"
    # 查图库验证 Chunk 节点数不翻倍
    records, _, _ = ensured_schema.execute_query(
        "MATCH (c:Chunk {document_id: $doc}) RETURN count(c) AS n",
        doc="test_idem.md", database_="neo4j",
    )
    assert records[0]["n"] == count1


# ── 错误：400 / 413 ──

def test_upload_unsupported_type(ensured_schema):
    client = _client(ensured_schema)
    resp = _upload(client, "test_bad.docx", b"fake docx content")
    assert resp.status_code == 400
    body = resp.json()
    assert "error" in body
    assert "不支持" in body["error"]["message"]


def test_upload_too_large(ensured_schema, monkeypatch):
    """超 MAX_UPLOAD_MB → 413。monkeypatch 降低上限加速，避免构造超大内容。"""
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "max_upload_mb", 1)
    client = _client(ensured_schema)
    big = b"x" * (2 * 1024 * 1024)  # 2MB > 1MB(临时上限)
    resp = _upload(client, "test_big.md", big)
    assert resp.status_code == 413


# ── 端到端贯通：chunk 反查 ──

def test_chunk_lookup_after_upload(ensured_schema):
    client = _client(ensured_schema)
    resp = _upload(client, "test_chunk.md", b"# Chunk\n\nBody text here.\n")
    assert resp.status_code == 200
    chunk_id = f"{resp.json()['documentId']}#0"
    r = client.get(f"/api/chunks/{chunk_id.replace('#', '%23')}")
    assert r.status_code == 200
    body = r.json()
    assert body["chunkId"] == chunk_id
    assert body["text"]


# ── 临时文件清理 ──

def test_temp_file_cleaned(ensured_schema):
    client = _client(ensured_schema)
    with patch("os.remove", wraps=os.remove) as mock_remove:
        _upload(client, "test_tmp.md", b"# Tmp\n\nContent.\n")
        # os.remove 至少被调用过（临时文件清理路径）
        assert mock_remove.called


# ── GET 列表/单文档：状态字段 ──

def test_list_documents_has_status_fields(ensured_schema):
    client = _client(ensured_schema)
    _upload(client, "test_list.md", b"# List\n\nDocument for list test.\n")
    resp = client.get("/api/documents")
    assert resp.status_code == 200
    docs = resp.json()
    test_docs = [d for d in docs if d["id"] == "test_list.md"]
    assert test_docs, "上传的文档未出现在列表"
    d = test_docs[0]
    assert d["name"] == "test_list.md"
    assert d["sourceType"] == "markdown"
    assert d["parseStatus"] == "parsed"
    assert d["indexStatus"] == "indexed"
    assert d["chunkCount"] >= 1


def test_get_document_detail(ensured_schema):
    client = _client(ensured_schema)
    _upload(client, "test_detail.md", b"# Detail\n\nSingle doc detail.\n")
    resp = client.get("/api/documents/test_detail.md")
    assert resp.status_code == 200
    d = resp.json()
    assert d["id"] == "test_detail.md"
    assert d["parseStatus"] == "parsed"


def test_get_missing_document_404(ensured_schema):
    client = _client(ensured_schema)
    resp = client.get("/api/documents/test_nonexistent.md")
    assert resp.status_code == 404
