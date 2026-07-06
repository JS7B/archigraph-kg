"""会话 CRUD 路由测试：四端点 happy path + 404。

用 TestClient + create_app，复用 ensured_schema 保证 schema 就绪。
测试会话用 conv_test 前缀，由 _clean 清理。
"""

from fastapi.testclient import TestClient

from app.conversations import add_message, create_conversation
from app.main import create_app
from app.runs import RunStore


def _client(ensured_schema):
    """构造 TestClient（复用 ensured_schema 的 driver，避免重复连库）。"""
    from app.clients.graph import get_driver

    app = create_app()
    app.state.neo4j = get_driver()
    app.state.runs = RunStore()
    return TestClient(app), app


def _seed_test_conversation(driver, title="api测试"):
    """创建会话并改 id 为 conv_test 前缀，保证被 _clean 清理。"""
    conv = create_conversation(driver, title=title)
    driver.execute_query(
        "MATCH (cv:Conversation {conversation_id: $old}) SET cv.conversation_id = $new",
        old=conv.conversation_id,
        new=f"conv_test_{conv.conversation_id[4:]}",
        database_="neo4j",
    )
    return f"conv_test_{conv.conversation_id[4:]}"


TEST_DIM = 8


def _vec():
    return [1.0] + [0.0] * (TEST_DIM - 1)


def test_create_conversation_endpoint(ensured_schema):
    client, _ = _client(ensured_schema)
    resp = client.post("/api/conversations", json={"title": "新建测试"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "新建测试"
    assert body["messageCount"] == 0
    assert body["messages"] == []
    assert body["conversationId"].startswith("conv_")
    # 改名 conv_test 前缀以便 _clean 清理（POST 创建的是随机 conv_ id）
    ensured_schema.execute_query(
        "MATCH (cv:Conversation {conversation_id: $old}) SET cv.conversation_id = $new",
        old=body["conversationId"],
        new=f"conv_test_{body['conversationId'][4:]}",
        database_="neo4j",
    )


def test_create_conversation_default_title(ensured_schema):
    client, _ = _client(ensured_schema)
    resp = client.post("/api/conversations", json={})
    assert resp.status_code == 200
    # 改名便于清理
    cid = resp.json()["conversationId"]
    ensured_schema.execute_query(
        "MATCH (cv:Conversation {conversation_id: $old}) SET cv.conversation_id = $new",
        old=cid, new=f"conv_test_{cid[4:]}", database_="neo4j",
    )


def test_list_conversations_endpoint(ensured_schema):
    _seed_test_conversation(ensured_schema, title="列表项A")
    client, _ = _client(ensured_schema)
    resp = client.get("/api/conversations")
    assert resp.status_code == 200
    items = resp.json()["items"]
    test_items = [i for i in items if i["conversationId"].startswith("conv_test_")]
    assert len(test_items) >= 1
    item = test_items[0]
    assert "title" in item and "createdAt" in item and "messageCount" in item


def test_get_conversation_with_messages(ensured_schema):
    cid = _seed_test_conversation(ensured_schema, title="详情")
    add_message(ensured_schema, cid, role="user", text="问", embedding=_vec())
    add_message(
        ensured_schema, cid, role="agent", text="答", embedding=_vec(),
        confidence="high",
    )
    client, _ = _client(ensured_schema)
    resp = client.get(f"/api/conversations/{cid}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["conversationId"] == cid
    assert body["messageCount"] == 2
    assert len(body["messages"]) == 2
    assert body["messages"][0]["role"] == "user"
    assert body["messages"][1]["role"] == "agent"
    assert body["messages"][1]["confidence"] == "high"


def test_get_conversation_not_found(ensured_schema):
    client, _ = _client(ensured_schema)
    resp = client.get("/api/conversations/conv_test_不存在")
    assert resp.status_code == 404


def test_rename_conversation_endpoint(ensured_schema):
    cid = _seed_test_conversation(ensured_schema, title="旧名字")
    client, _ = _client(ensured_schema)
    resp = client.patch(f"/api/conversations/{cid}", json={"title": "  新名字  "})
    assert resp.status_code == 200
    body = resp.json()
    assert body["conversationId"] == cid
    assert body["title"] == "新名字"  # 前后空白被 strip
    # 详情接口读到新标题
    assert client.get(f"/api/conversations/{cid}").json()["title"] == "新名字"


def test_rename_conversation_blank_title(ensured_schema):
    cid = _seed_test_conversation(ensured_schema, title="保持原名")
    client, _ = _client(ensured_schema)
    resp = client.patch(f"/api/conversations/{cid}", json={"title": "   "})
    assert resp.status_code == 422
    assert client.get(f"/api/conversations/{cid}").json()["title"] == "保持原名"


def test_rename_conversation_not_found(ensured_schema):
    client, _ = _client(ensured_schema)
    resp = client.patch("/api/conversations/conv_test_不存在", json={"title": "x"})
    assert resp.status_code == 404


def test_delete_conversation_endpoint(ensured_schema):
    cid = _seed_test_conversation(ensured_schema, title="待删")
    client, _ = _client(ensured_schema)
    resp = client.delete(f"/api/conversations/{cid}")
    assert resp.status_code == 200
    assert resp.json() == {"deleted": True}
    # 再删应 404
    resp2 = client.delete(f"/api/conversations/{cid}")
    assert resp2.status_code == 404
