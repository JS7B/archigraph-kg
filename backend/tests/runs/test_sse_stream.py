"""SSE stream 端点冒烟：用 TestClient 直接测 /events/stream 的流式 generator。

不走真实 uvicorn（子进程调试成本高），而是 mock run_chat 让它 emit 事件后，
用 TestClient 订阅 stream 端点，确认能收到 SSE 格式（data: {...}）的事件流。
这是 /events（历史）测试之外，对 stream generator 本身的验证。
"""

from fastapi.testclient import TestClient

from app.clients.graph import get_driver
from app.main import create_app
from app.routers import chat as chat_mod
from app.runs import RunStore
from app.runs.models import RunEvent, RunStatus, Stage


async def _fake_run_chat(driver, store, run_id, question, conversation_id):
    store.append_event(run_id, RunEvent(stage=Stage.SEARCHING))
    store.append_event(
        run_id,
        RunEvent(
            stage=Stage.IDLE,
            status=RunStatus.SUCCEEDED,
            answer={"question": question, "text": "ok", "citations": []},
        ),
    )


def test_sse_stream_format(monkeypatch):
    from app.conversations import Conversation

    monkeypatch.setattr(chat_mod, "run_chat", _fake_run_chat)
    # mock create_conversation 避免真连库建会话
    monkeypatch.setattr(
        chat_mod, "create_conversation",
        lambda driver, *, title="新会话": Conversation(conversation_id="conv_test_sse", title=title),
    )
    app = create_app()
    app.state.neo4j = get_driver()
    app.state.runs = RunStore()
    client = TestClient(app)

    run_id = client.post("/api/chat", json={"question": "x"}).json()["runId"]
    # stream 端点：TestClient 会把整个流读完（同步消费）
    with client.stream("GET", f"/api/runs/{run_id}/events/stream") as resp:
        assert resp.status_code == 200
        body = "".join(line.decode() for line in resp.iter_bytes())
    # SSE 格式：应含 data: 行，且包含 stage 字段
    assert "data:" in body
    assert "searching" in body
    assert "succeeded" in body
    # 终态事件应带 answer
    assert "ok" in body
    # 事件应携带 seq 序号（前端断线重连去重的依据）
    assert '"seq": 1' in body
    assert '"seq": 2' in body
