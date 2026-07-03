"""文档库路由测试（B 板块：异步上传/删除 + SSE 进度）。

POST/DELETE 改异步：立即返回 runId，后台任务跑入库/删除。测试策略：
- mock run_ingest/run_delete（后台任务内部 LLM/parse 已被各自任务测试覆盖），
  让它直接向 store emit 完整事件序列，验证响应契约 + SSE 流。
- GET 列表/单文档仍走真实 Neo4j（需要 Document 节点，测试里手动写入）。
- 400/413 在起后台任务前就抛，无需 mock。
"""

import pytest
from fastapi.testclient import TestClient

from app.extraction.models import ExtractionStats
from app.main import create_app
from app.routers import documents as docs_mod
from app.runs import RunStore
from app.runs.models import RunEvent, RunStatus, Stage

TEST_DIM = 8


def _fake_stats(doc):
    return ExtractionStats(
        document_id=doc.document_id,
        entity_count=3,
        relation_count=2,
        mention_count=3,
        failed_chunks=[],
    )


def _make_run_ingest_that_succeeds():
    """构造一个假的 run_ingest：直接 emit 完整成功事件序列，不跑真实链路。"""

    async def _fake(driver, store, run_id, file_bytes, filename, doc_type):
        # 与真实 run_ingest 的阶段序列保持一致：向量写入(indexing)先于逐 chunk 抽取(extracting)
        for stage, status in [
            (Stage.UPLOADING, RunStatus.RUNNING),
            (Stage.PARSING, RunStatus.RUNNING),
            (Stage.INDEXING, RunStatus.RUNNING),
            (Stage.EXTRACTING, RunStatus.RUNNING),
            (Stage.INDEXING, RunStatus.RUNNING),
            (Stage.IDLE, RunStatus.SUCCEEDED),
        ]:
            store.append_event(run_id, RunEvent(stage=stage, status=status))

    return _fake


async def _fake_run_delete(driver, store, run_id, document_id):
    store.append_event(run_id, RunEvent(stage=Stage.DELETING, status=RunStatus.RUNNING))
    store.append_event(run_id, RunEvent(stage=Stage.IDLE, status=RunStatus.SUCCEEDED))


@pytest.fixture(autouse=True)
def _patch_tasks(monkeypatch):
    """全局 mock 后台任务，避免真实 LLM/parse 调用（任务内部逻辑各自有测试）。"""
    monkeypatch.setattr(docs_mod, "run_ingest", _make_run_ingest_that_succeeds())
    monkeypatch.setattr(docs_mod, "run_delete", _fake_run_delete)


def _client():
    """构造 TestClient：不走 lifespan，手动注入 RunStore（driver 由 conftest 的
    ensured_schema 所在 fixture 链提供——但路由用 request.app.state.neo4j，
    这里也注入一份测试 driver）。"""
    from app.clients.graph import get_driver

    app = create_app()
    app.state.neo4j = get_driver()
    app.state.runs = RunStore()
    return TestClient(app), app


def _upload(client, name: str, content: bytes):
    return client.post(
        "/api/documents",
        files={"file": (name, content, "application/octet-stream")},
    )


# ── 异步上传：返回 runId ──

def test_upload_returns_run_id_immediately(ensured_schema):
    client, _ = _client()
    resp = _upload(client, "test_md_doc.md", b"# Test\n\nBody.\n")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "runId" in body
    assert body["documentId"] == "test_md_doc.md"
    assert body["documentName"] == "test_md_doc.md"


def test_upload_eventual_success_via_sse(ensured_schema):
    """上传后 SSE 流应收到完整事件序列并以 succeeded 终态关闭。"""
    client, app = _client()
    resp = _upload(client, "test_sse.md", b"# SSE\n\nEvent stream.\n")
    run_id = resp.json()["runId"]
    # BackgroundTasks 在响应发送后由 TestClient 同步执行，此时任务已完成
    r = client.get(f"/api/runs/{run_id}/events")
    assert r.status_code == 200
    events = r.json()
    stages = [e["stage"] for e in events]
    assert stages == ["uploading", "parsing", "indexing", "extracting", "indexing", "idle"]
    assert events[-1]["status"] == "succeeded"


def test_upload_txt(ensured_schema):
    client, _ = _client()
    resp = _upload(client, "test_txt.txt", b"Plain text content.\n")
    assert resp.status_code == 200
    assert "runId" in resp.json()


# ── 错误：400 / 413（起任务前就抛）──

def test_upload_unsupported_type(ensured_schema):
    client, _ = _client()
    resp = _upload(client, "test_bad.docx", b"fake")
    assert resp.status_code == 400
    assert "不支持" in resp.json()["error"]["message"]


def test_upload_too_large(ensured_schema, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "max_upload_mb", 1)
    client, _ = _client()
    resp = _upload(client, "test_big.md", b"x" * (2 * 1024 * 1024))
    assert resp.status_code == 413


# ── DELETE 异步 ──

def test_delete_requires_confirm(ensured_schema):
    """B2：删除是危险操作，不带 confirm=true 应被拒（防误删/恶意 curl）。"""
    client, _ = _client()
    resp = client.delete("/api/documents/test_del.md")
    assert resp.status_code == 400


def test_delete_returns_run_id(ensured_schema):
    client, _ = _client()
    resp = client.delete("/api/documents/test_del.md?confirm=true")
    assert resp.status_code == 200
    body = resp.json()
    assert "runId" in body
    assert body["documentId"] == "test_del.md"
    r = client.get(f"/api/runs/{body['runId']}/events")
    stages = [e["stage"] for e in r.json()]
    assert stages == ["deleting", "idle"]
    assert r.json()[-1]["status"] == "succeeded"


# ── GET 列表/单文档（走真实 Neo4j，需手动写 Document 节点）──

def test_list_and_get_document(ensured_schema):
    ensured_schema.execute_query(
        """
        MERGE (d:Document {document_id: 'test_listdoc.md'})
          SET d.name='test_listdoc.md', d.source_type='markdown',
              d.parse_status='parsed', d.index_status='indexed', d.chunk_count=3
        """,
        database_="neo4j",
    )
    client, _ = _client()
    r = client.get("/api/documents")
    docs = [d for d in r.json() if d["id"] == "test_listdoc.md"]
    assert docs
    d = docs[0]
    assert d["parseStatus"] == "parsed"
    assert d["indexStatus"] == "indexed"
    assert d["chunkCount"] == 3

    r2 = client.get("/api/documents/test_listdoc.md")
    assert r2.status_code == 200
    assert r2.json()["id"] == "test_listdoc.md"


def test_get_missing_document_404(ensured_schema):
    client, _ = _client()
    assert client.get("/api/documents/test_nope.md").status_code == 404
