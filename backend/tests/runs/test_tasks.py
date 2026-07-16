"""run_chat 后台任务单元测试：Agentic RAG 主路径 + 降级路径 + 失败路径 + 多轮记忆。

run_chat 现在签名含 conversation_id（多轮记忆）。三组原有用例适配新签名，新增会话
端到端用例（mock LLM + seed 图谱，验证历史读出 + 本轮写回）。不连真实 LLM。
"""

import pytest

from app.extraction.models import ExtractionStats
from app.parsing.models import ParsedDocument
from app.qa.agent import ToolCallingUnsupported
from app.qa.models import Answer, Citation
from app.runs import RunStore
from app.runs import tasks as tasks_mod
from app.runs.models import RunKind, RunStatus, Stage


def _fake_answer(*args, **kwargs):
    return Answer(
        text="mock answer [1]",
        confidence="medium",
        citations=[Citation(index=1, chunk_id="c1", document_id="d1", location="loc", snippet="evi")],
    )


@pytest.mark.anyio
async def test_run_ingest_emits_completed_extractable_progress(monkeypatch):
    doc = ParsedDocument(
        document_id="doc.txt",
        source_path="temp.txt",
        doc_type="text",
        raw_text="",
        chunks=[],
    )

    monkeypatch.setattr(tasks_mod, "parse_file", lambda *args, **kwargs: doc)
    monkeypatch.setattr(tasks_mod, "embed_chunks", lambda *args, **kwargs: [])
    monkeypatch.setattr(tasks_mod, "ingest_document", lambda *args, **kwargs: None)

    def fake_extract_and_ingest(driver, parsed_doc, **kwargs):
        kwargs["on_progress"](1, 2)
        kwargs["on_progress"](2, 2)
        return ExtractionStats(
            document_id=parsed_doc.document_id,
            entity_count=0,
            relation_count=0,
            mention_count=0,
        )

    monkeypatch.setattr(tasks_mod, "extract_and_ingest", fake_extract_and_ingest)
    store = RunStore()
    run = store.create_run(RunKind.INGEST)

    await tasks_mod.run_ingest(
        driver=None,
        store=store,
        run_id=run.id,
        file_bytes=b"content",
        filename="doc.txt",
        doc_type="text",
    )

    extracting = [event for event in run.events if event.stage == Stage.EXTRACTING]
    assert [event.message for event in extracting] == [
        "已从分块 1/2 中抽取实体与关系",
        "已从分块 2/2 中抽取实体与关系",
    ]
    assert run.status == RunStatus.SUCCEEDED


@pytest.mark.anyio
async def test_run_chat_agentic_forwards_on_step_events(monkeypatch):
    """主路径：answer_question_agentic 经 on_event 发出逐步事件，run_chat 转发 + 终态 IDLE。"""

    def _agentic(driver, question, *, history=None, on_event=None, **kw):
        if on_event:
            on_event(Stage.SEARCHING, "向量检索")
            on_event(Stage.LINKING, "扩展实体关系")
            on_event(Stage.WRITING, "生成带引用回答")
        return _fake_answer()

    monkeypatch.setattr(tasks_mod, "answer_question_agentic", _agentic)
    # stub 会话读写（不连图谱），返回空历史、空写入
    monkeypatch.setattr(tasks_mod, "get_messages", lambda *a, **kw: [])
    monkeypatch.setattr(tasks_mod, "add_message", lambda *a, **kw: None)
    monkeypatch.setattr(tasks_mod, "embed_texts", lambda texts: [[0.1] * 8])
    store = RunStore()
    run = store.create_run(RunKind.CHAT)

    await tasks_mod.run_chat(
        driver=None, store=store, run_id=run.id, question="test", conversation_id="conv_test_x"
    )

    stages = [e.stage for e in run.events]
    assert stages == [Stage.SEARCHING, Stage.LINKING, Stage.WRITING, Stage.IDLE]
    assert run.status == RunStatus.SUCCEEDED
    terminal = run.events[-1]
    assert terminal.answer is not None
    assert terminal.answer["text"] == "mock answer [1]"


@pytest.mark.anyio
async def test_run_chat_falls_back_to_linear_on_unsupported_tools(monkeypatch):
    """降级路径：agent 抛 ToolCallingUnsupported 时回退线性版，发固定三事件 + 终态。"""

    def _unsupported(*a, **kw):
        raise ToolCallingUnsupported("tools not supported")

    monkeypatch.setattr(tasks_mod, "answer_question_agentic", _unsupported)
    monkeypatch.setattr(tasks_mod, "answer_question", _fake_answer)
    monkeypatch.setattr(tasks_mod, "get_messages", lambda *a, **kw: [])
    monkeypatch.setattr(tasks_mod, "add_message", lambda *a, **kw: None)
    monkeypatch.setattr(tasks_mod, "embed_texts", lambda texts: [[0.1] * 8])
    store = RunStore()
    run = store.create_run(RunKind.CHAT)

    await tasks_mod.run_chat(
        driver=None, store=store, run_id=run.id, question="test", conversation_id="conv_test_y"
    )

    stages = [e.stage for e in run.events]
    assert stages == [Stage.SEARCHING, Stage.CHECKING, Stage.WRITING, Stage.IDLE]
    assert run.status == RunStatus.SUCCEEDED
    assert run.events[-1].answer is not None


@pytest.mark.anyio
async def test_run_chat_failure_emits_error(monkeypatch):
    """失败路径：agent 抛普通异常时，run_chat emit error 终态（不吞异常）。"""

    def _boom(*a, **kw):
        raise RuntimeError("LLM down")

    monkeypatch.setattr(tasks_mod, "answer_question_agentic", _boom)
    monkeypatch.setattr(tasks_mod, "get_messages", lambda *a, **kw: [])
    store = RunStore()
    run = store.create_run(RunKind.CHAT)

    await tasks_mod.run_chat(
        driver=None, store=store, run_id=run.id, question="x", conversation_id="conv_test_z"
    )

    assert run.status == RunStatus.FAILED
    assert run.events[-1].stage == Stage.ERROR
    assert "LLM down" in run.events[-1].message


@pytest.mark.anyio
async def test_run_chat_reads_history_and_writes_back(monkeypatch, ensured_schema):
    """多轮记忆端到端：run_chat 应读出历史注入 agent、并把本轮 user/agent 写回图谱。

    seed 一条历史消息，验证 history 传给了 agent；验证本轮写回两条消息（turn_index 自增）。
    """
    driver = ensured_schema
    # seed 历史会话 + 一条历史消息（conv_test 前缀，被 _clean 清理）
    from app.conversations import add_message, create_conversation, get_messages

    conv = create_conversation(driver, title="历史会话")
    driver.execute_query(
        "MATCH (cv:Conversation {conversation_id: $old}) SET cv.conversation_id = $new",
        old=conv.conversation_id, new=f"conv_test_{conv.conversation_id[4:]}",
        database_="neo4j",
    )
    cid = f"conv_test_{conv.conversation_id[4:]}"
    add_message(driver, cid, role="user", text="历史问题", embedding=[0.1] * 8)

    captured_history = []

    def _agentic(d, question, *, history=None, on_event=None, **kw):
        captured_history.extend(history or [])
        return _fake_answer()

    monkeypatch.setattr(tasks_mod, "answer_question_agentic", _agentic)
    monkeypatch.setattr(tasks_mod, "embed_texts", lambda texts: [[0.1] * 8])
    store = RunStore()
    run = store.create_run(RunKind.CHAT)

    await tasks_mod.run_chat(
        driver=driver, store=store, run_id=run.id, question="追问", conversation_id=cid
    )

    # 历史被读出并注入（至少 1 条历史）
    assert len(captured_history) >= 1
    assert captured_history[0]["role"] == "user"
    # 本轮两条消息写回（原 1 条历史 + 本轮 user + agent = 3 条）
    messages = get_messages(driver, cid)
    assert len(messages) == 3
    roles = [m.role for m in messages]
    assert roles == ["user", "user", "agent"]  # 历史 user + 本轮 user + 本轮 agent
