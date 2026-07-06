"""chat 路由测试（B 板块：异步问答 + SSE 终态带 answer）。

POST /api/chat 改异步：返回 runId，后台 run_chat 跑检索+生成。
测试 mock run_chat 让它 emit 含 answer 的终态事件，验证响应契约 + SSE 终态带 answer。
chunk 反查（GET /api/chunks/{id}）走真实库。
"""

import pytest
from fastapi.testclient import TestClient

from app.clients.graph import get_driver
from app.conversations import Conversation
from app.main import create_app
from app.routers import chat as chat_mod
from app.runs import RunStore
from app.runs.models import RunEvent, RunStatus, Stage


async def _fake_run_chat(driver, store, run_id, question, conversation_id):
    """假问答任务：直接 emit 含 answer 的终态事件（方案 a）。"""
    store.append_event(
        run_id, RunEvent(stage=Stage.SEARCHING, status=RunStatus.RUNNING)
    )
    store.append_event(
        run_id, RunEvent(stage=Stage.CHECKING, status=RunStatus.RUNNING)
    )
    store.append_event(
        run_id,
        RunEvent(
            stage=Stage.IDLE,
            status=RunStatus.SUCCEEDED,
            answer={
                "question": question,
                "text": "mock answer [1]",
                "citations": [
                    {"chunkId": "c1", "index": 1, "text": "evidence"}
                ],
            },
        ),
    )


def _fake_create_conversation(driver, *, title="新会话"):
    """假建会话：返回固定 conv_test 前缀（被 _clean 清理），不真连库。"""
    return Conversation(conversation_id="conv_test_fake", title=title)


@pytest.fixture(autouse=True)
def _patch_run_chat(monkeypatch):
    monkeypatch.setattr(chat_mod, "run_chat", _fake_run_chat)
    monkeypatch.setattr(chat_mod, "create_conversation", _fake_create_conversation)
    # 追问路径会查/改会话标题，默认 mock 成"会话不存在"（不真连库）
    monkeypatch.setattr(chat_mod, "get_conversation", lambda driver, cid: None)
    monkeypatch.setattr(
        chat_mod, "rename_conversation", lambda driver, cid, title: None
    )


def _client():
    app = create_app()
    app.state.neo4j = get_driver()
    app.state.runs = RunStore()
    return TestClient(app), app


def test_chat_returns_run_id_and_conversation_id():
    """首问：自动建会话，响应含 runId + conversationId。"""
    client, _ = _client()
    resp = client.post("/api/chat", json={"question": "什么是 GraphRAG？"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "runId" in body
    assert "conversationId" in body
    assert body["conversationId"]


def test_chat_with_existing_conversation():
    """追问：传 conversationId 透传，响应返回同一个 id。"""
    client, _ = _client()
    resp = client.post(
        "/api/chat",
        json={"question": "追问", "conversationId": "conv_test_existing"},
    )
    assert resp.status_code == 200
    assert resp.json()["conversationId"] == "conv_test_existing"


def test_chat_first_question_titles_conversation(monkeypatch):
    """首问自动建会话：标题 = 首句提问截断 20 字。"""
    captured = {}

    def _capture_create(driver, *, title="新会话"):
        captured["title"] = title
        return Conversation(conversation_id="conv_test_fake", title=title)

    monkeypatch.setattr(chat_mod, "create_conversation", _capture_create)
    client, _ = _client()
    question = "这是一句超过二十个字的很长很长的提问内容用来验证截断"
    resp = client.post("/api/chat", json={"question": question})
    assert resp.status_code == 200
    assert captured["title"] == question[:20]


def test_chat_renames_default_titled_empty_conversation(monkeypatch):
    """「新建」出的空会话（缺省标题）首问时用问题改名。"""
    renamed = {}
    monkeypatch.setattr(
        chat_mod,
        "get_conversation",
        lambda driver, cid: Conversation(
            conversation_id=cid, title="新会话", message_count=0
        ),
    )
    monkeypatch.setattr(
        chat_mod,
        "rename_conversation",
        lambda driver, cid, title: renamed.update({"id": cid, "title": title}),
    )
    client, _ = _client()
    resp = client.post(
        "/api/chat",
        json={"question": "第一句提问", "conversationId": "conv_test_empty"},
    )
    assert resp.status_code == 200
    assert renamed == {"id": "conv_test_empty", "title": "第一句提问"}


def test_chat_keeps_custom_title_on_first_question(monkeypatch):
    """空会话但标题已被手动改过：首问不覆盖。"""
    renamed = {}
    monkeypatch.setattr(
        chat_mod,
        "get_conversation",
        lambda driver, cid: Conversation(
            conversation_id=cid, title="我的自定义标题", message_count=0
        ),
    )
    monkeypatch.setattr(
        chat_mod,
        "rename_conversation",
        lambda driver, cid, title: renamed.update({"title": title}),
    )
    client, _ = _client()
    resp = client.post(
        "/api/chat",
        json={"question": "第一句提问", "conversationId": "conv_test_custom"},
    )
    assert resp.status_code == 200
    assert renamed == {}


def test_chat_sse_terminal_event_carries_answer():
    """SSE 终态事件应带 answer 字段（前端方案 a，少一次往返）。"""
    client, _ = _client()
    run_id = client.post("/api/chat", json={"question": "test"}).json()["runId"]
    events = client.get(f"/api/runs/{run_id}/events").json()
    assert events[-1]["status"] == "succeeded"
    assert events[-1]["answer"]["text"] == "mock answer [1]"
    assert events[-1]["answer"]["citations"][0]["chunkId"] == "c1"
    stages = [e["stage"] for e in events]
    assert stages == ["searching", "checking", "idle"]


def test_chunk_lookup(ensured_schema):
    """GET /api/chunks/{id} 走真实库。"""
    ensured_schema.execute_query(
        """
        MERGE (d:Document {document_id: 'test_chunkdoc.md'})-[:HAS_CHUNK]->
              (c:Chunk {chunk_id: 'test_chunkdoc.md#0'})
          SET c.text='chunk body', c.page=1, c.char_start=0, c.char_end=10,
              c.heading_path=['H1'], c.document_id='test_chunkdoc.md'
        """,
        database_="neo4j",
    )
    client, _ = _client()
    r = client.get("/api/chunks/test_chunkdoc.md%230")
    assert r.status_code == 200
    body = r.json()
    assert body["chunkId"] == "test_chunkdoc.md#0"
    assert body["text"] == "chunk body"
