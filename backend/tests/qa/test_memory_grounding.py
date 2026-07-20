"""追问指代消歧与共享检索问题的确定性测试。"""

from types import SimpleNamespace

import httpx
import pytest
from openai import BadRequestError

from app.graph.search import ChunkHit
from app.qa import agent as agent_mod
from app.qa import pipeline as pipeline_mod
from app.qa import question_rewrite as rewrite_mod
from app.qa.agent import answer_question_agentic
from app.qa.models import Answer
from app.qa.pipeline import answer_question
from app.qa.prompt import ANSWER_SYSTEM_PROMPT, build_answer_messages
from app.runs import RunStore
from app.runs import tasks as tasks_mod
from app.runs.models import RunKind, RunStatus


ORIGINAL = "它为什么适合这个项目？"
STANDALONE = "Neo4j 为什么适合 Archigraph 项目？"
HISTORY = [
    {"role": "user", "content": "Archigraph 使用什么图数据库？"},
    {"role": "assistant", "content": "Archigraph 使用 Neo4j。"},
]


@pytest.fixture
def anyio_backend():
    """聚焦门禁不加载顶层 conftest，显式只使用已安装的 asyncio 后端。"""
    return "asyncio"


def _hit() -> ChunkHit:
    return ChunkHit(
        chunk_id="doc#0",
        document_id="doc",
        chunk_index=0,
        text="Neo4j 同时支持图关系和向量索引。",
        char_start=0,
        char_end=19,
        score=0.9,
    )


def _assistant_message(*, tool_calls=None, content=""):
    return SimpleNamespace(content=content, tool_calls=tool_calls or [])


def test_no_history_skips_rewrite_and_preserves_single_turn_agent_messages(monkeypatch):
    rewrite_calls = []

    def _unexpected_rewrite(messages):
        rewrite_calls.append(messages)
        raise AssertionError("无历史时不应调用重写模型")

    monkeypatch.setattr(rewrite_mod.llm, "chat", _unexpected_rewrite)
    assert rewrite_mod.resolve_retrieval_question(ORIGINAL, []) == ORIGINAL
    assert rewrite_calls == []

    planner_messages = []

    def _planner(messages, **kwargs):
        planner_messages.extend(messages)
        return _assistant_message()

    monkeypatch.setattr(agent_mod.llm, "chat_with_tools", _planner)
    answer = answer_question_agentic(None, ORIGINAL)

    assert planner_messages[0]["role"] == "system"
    assert planner_messages[1] == {"role": "user", "content": ORIGINAL}
    assert len(planner_messages) == 2
    assert answer.confidence == "low"
    assert answer.citations == []

    final_messages = build_answer_messages(ORIGINAL, "【文档片段】\n[1] 证据")
    assert final_messages == [
        {"role": "system", "content": ANSWER_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"【文档片段】\n[1] 证据\n\n【问题】\n{ORIGINAL}"
                "\n\n请基于上述文档片段作答，并用 [编号] 标注引用。"
            ),
        },
    ]


def test_rewrite_resolves_reference_strips_and_caps_output(monkeypatch):
    captured = []
    monkeypatch.setattr(
        rewrite_mod.llm,
        "chat",
        lambda messages: captured.extend(messages) or f"  {STANDALONE}  ",
    )

    assert rewrite_mod.resolve_retrieval_question(ORIGINAL, HISTORY) == STANDALONE
    assert captured[0]["role"] == "system"
    assert "只消解指代" in captured[0]["content"]
    assert "不得回答" in captured[0]["content"]
    assert captured[1:3] == HISTORY
    assert captured[-1]["role"] == "user"
    assert ORIGINAL in captured[-1]["content"]

    monkeypatch.setattr(rewrite_mod.llm, "chat", lambda messages: "x" * 1001)
    assert rewrite_mod.resolve_retrieval_question(ORIGINAL, HISTORY) == "x" * 1000


@pytest.mark.parametrize(
    "rewrite_result",
    ["", "   ", None, RuntimeError("rewrite timeout")],
)
def test_rewrite_failure_or_empty_output_falls_back_to_original_once(
    monkeypatch, rewrite_result
):
    calls = 0

    def _rewrite(messages):
        nonlocal calls
        calls += 1
        if isinstance(rewrite_result, Exception):
            raise rewrite_result
        return rewrite_result

    monkeypatch.setattr(rewrite_mod.llm, "chat", _rewrite)

    assert rewrite_mod.resolve_retrieval_question(ORIGINAL, HISTORY) == ORIGINAL
    assert calls == 1


def test_agentic_planning_and_final_synthesis_use_grounded_question(monkeypatch):
    planner_messages = []
    final_messages = []
    tool_call = SimpleNamespace(
        id="call-1",
        function=SimpleNamespace(
            name="vector_search", arguments='{"query":"Neo4j Archigraph"}'
        ),
    )
    replies = iter(
        [
            _assistant_message(tool_calls=[tool_call]),
            _assistant_message(content="证据足够"),
        ]
    )

    def _planner(messages, **kwargs):
        if not planner_messages:
            planner_messages.extend(messages)
        return next(replies)

    monkeypatch.setattr(agent_mod.llm, "chat_with_tools", _planner)
    monkeypatch.setattr(agent_mod, "_run_vector_search", lambda *args, **kwargs: [_hit()])
    monkeypatch.setattr(
        agent_mod.llm,
        "chat",
        lambda messages: final_messages.extend(messages) or "Neo4j 适合该项目。[1]",
    )

    answer = answer_question_agentic(
        None,
        ORIGINAL,
        retrieval_question=STANDALONE,
        history=HISTORY,
    )

    assert planner_messages[1:3] == HISTORY
    assert planner_messages[-1] == {"role": "user", "content": STANDALONE}
    assert [message["role"] for message in final_messages] == [
        "system",
        "user",
        "assistant",
        "user",
    ]
    final_user = final_messages[-1]["content"]
    assert "【文档片段】" in final_user
    assert "Neo4j 同时支持图关系和向量索引" in final_user
    assert f"【用户原始问题】\n{ORIGINAL}" in final_user
    assert f"【消歧后的独立问题】\n{STANDALONE}" in final_user
    assert [citation.chunk_id for citation in answer.citations] == ["doc#0"]


def test_linear_fallback_retrieves_with_same_grounded_question(monkeypatch):
    embedded = []
    reranked = []
    final_messages = []
    monkeypatch.setattr(
        pipeline_mod.llm,
        "embed",
        lambda texts: embedded.extend(texts) or [[0.1] * 8],
    )
    monkeypatch.setattr(
        pipeline_mod,
        "search_chunks",
        lambda *args, **kwargs: [_hit()],
    )
    monkeypatch.setattr(
        pipeline_mod,
        "rerank_chunks",
        lambda query, hits, **kwargs: reranked.append(query) or hits,
    )
    monkeypatch.setattr(
        pipeline_mod,
        "expand_entities",
        lambda *args, **kwargs: SimpleNamespace(paths=[]),
    )
    monkeypatch.setattr(
        pipeline_mod.llm,
        "chat",
        lambda messages: final_messages.extend(messages) or "结论。[1]",
    )

    answer = answer_question(
        None,
        ORIGINAL,
        retrieval_question=STANDALONE,
        history=HISTORY,
    )

    assert embedded == [STANDALONE]
    assert reranked == [STANDALONE]
    assert final_messages[1:3] == HISTORY
    assert ORIGINAL in final_messages[-1]["content"]
    assert STANDALONE in final_messages[-1]["content"]
    assert [citation.chunk_id for citation in answer.citations] == ["doc#0"]


def test_final_answer_prompt_keeps_history_separate_from_document_evidence():
    messages = build_answer_messages(
        ORIGINAL,
        "【文档片段】\n[1] 文档证据",
        history=HISTORY,
        retrieval_question=STANDALONE,
    )

    assert messages[1:3] == HISTORY
    assert [message["role"] for message in messages] == [
        "system",
        "user",
        "assistant",
        "user",
    ]
    assert "历史仅用于理解问题" in messages[0]["content"]
    assert "文档证据" in messages[-1]["content"]
    assert HISTORY[1]["content"] not in messages[-1]["content"]


def test_empty_evidence_refuses_even_when_history_contains_an_answer(monkeypatch):
    monkeypatch.setattr(
        agent_mod.llm,
        "chat_with_tools",
        lambda *args, **kwargs: _assistant_message(content="可直接回答"),
    )
    monkeypatch.setattr(
        agent_mod.llm,
        "chat",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("空证据不应调用最终生成")
        ),
    )

    answer = answer_question_agentic(
        None,
        ORIGINAL,
        retrieval_question=STANDALONE,
        history=HISTORY,
    )

    assert answer.text == "根据现有资料无法回答。"
    assert answer.confidence == "low"
    assert answer.citations == []


@pytest.mark.anyio
async def test_run_chat_without_history_never_invokes_rewriter(monkeypatch):
    rewrite_calls = []
    retrieval_questions = []
    monkeypatch.setattr(tasks_mod, "get_messages", lambda *args, **kwargs: [])

    def _unexpected_rewrite(*args, **kwargs):
        rewrite_calls.append((args, kwargs))
        raise AssertionError("无历史的任务入口不应执行 rewrite")

    def _agentic(driver, question, **kwargs):
        retrieval_questions.append(kwargs["retrieval_question"])
        return Answer(text="根据现有资料无法回答。", confidence="low", citations=[])

    monkeypatch.setattr(tasks_mod, "resolve_retrieval_question", _unexpected_rewrite)
    monkeypatch.setattr(tasks_mod, "answer_question_agentic", _agentic)
    monkeypatch.setattr(tasks_mod, "append_turn", lambda *args, **kwargs: None)
    monkeypatch.setattr(tasks_mod, "embed_texts", lambda texts: [[0.1] * 8] * 2)
    store = RunStore()
    run = store.create_run(RunKind.CHAT)

    await tasks_mod.run_chat(
        None,
        store,
        run.id,
        ORIGINAL,
        "conv_test_no_history",
    )

    assert rewrite_calls == []
    assert retrieval_questions == [None]
    assert run.status == RunStatus.SUCCEEDED


@pytest.mark.anyio
async def test_rewrite_failure_inside_chat_semaphore_keeps_run_alive(monkeypatch):
    class TrackingSemaphore:
        active = False

        async def __aenter__(self):
            self.active = True

        async def __aexit__(self, *args):
            self.active = False

    semaphore = TrackingSemaphore()
    rewrite_calls = []
    retrieval_questions = []
    history_messages = [SimpleNamespace(role="user", text="上一轮问题")]
    monkeypatch.setattr(tasks_mod, "_LLM_SEMAPHORE", semaphore)
    monkeypatch.setattr(
        tasks_mod, "get_messages", lambda *args, **kwargs: history_messages
    )

    def _failed_rewrite(messages):
        assert semaphore.active is True
        rewrite_calls.append(messages)
        raise TimeoutError("rewrite timeout")

    def _agentic(driver, question, **kwargs):
        assert semaphore.active is True
        retrieval_questions.append(kwargs["retrieval_question"])
        return Answer(text="根据现有资料无法回答。", confidence="low", citations=[])

    monkeypatch.setattr(rewrite_mod.llm, "chat", _failed_rewrite)
    monkeypatch.setattr(tasks_mod, "answer_question_agentic", _agentic)
    monkeypatch.setattr(tasks_mod, "append_turn", lambda *args, **kwargs: None)
    monkeypatch.setattr(tasks_mod, "embed_texts", lambda texts: [[0.1] * 8] * 2)
    store = RunStore()
    run = store.create_run(RunKind.CHAT)

    await tasks_mod.run_chat(
        None,
        store,
        run.id,
        ORIGINAL,
        "conv_test_rewrite_failure",
    )

    assert len(rewrite_calls) == 1
    assert retrieval_questions == [ORIGINAL]
    assert semaphore.active is False
    assert run.status == RunStatus.SUCCEEDED


@pytest.mark.anyio
async def test_bad_request_fallback_reuses_one_rewrite(monkeypatch):
    rewrite_calls = []
    agent_questions = []
    fallback_questions = []
    history_messages = [
        SimpleNamespace(role="user", text=HISTORY[0]["content"]),
        SimpleNamespace(role="agent", text=HISTORY[1]["content"]),
    ]

    monkeypatch.setattr(
        tasks_mod, "get_messages", lambda *args, **kwargs: history_messages
    )
    monkeypatch.setattr(
        tasks_mod,
        "resolve_retrieval_question",
        lambda question, history: (
            rewrite_calls.append((question, history)) or STANDALONE
        ),
    )

    def _bad_request(messages, **kwargs):
        raise BadRequestError(
            message="tools unsupported",
            response=httpx.Response(
                400, request=httpx.Request("POST", "https://example.test/chat")
            ),
            body={"error": "tools unsupported"},
        )

    monkeypatch.setattr(agent_mod.llm, "chat_with_tools", _bad_request)

    def _agentic(driver, question, **kwargs):
        agent_questions.append(kwargs["retrieval_question"])
        return answer_question_agentic(driver, question, **kwargs)

    def _linear(driver, question, **kwargs):
        fallback_questions.append(kwargs["retrieval_question"])
        return Answer(text="根据现有资料无法回答。", confidence="low", citations=[])

    monkeypatch.setattr(tasks_mod, "answer_question_agentic", _agentic)
    monkeypatch.setattr(tasks_mod, "answer_question", _linear)
    monkeypatch.setattr(tasks_mod, "append_turn", lambda *args, **kwargs: None)
    monkeypatch.setattr(tasks_mod, "embed_texts", lambda texts: [[0.1] * 8] * 2)
    store = RunStore()
    run = store.create_run(RunKind.CHAT)

    await tasks_mod.run_chat(
        None,
        store,
        run.id,
        ORIGINAL,
        "conv_test_memory",
    )

    assert len(rewrite_calls) == 1
    assert agent_questions == [STANDALONE]
    assert fallback_questions == [STANDALONE]
    assert run.status == RunStatus.SUCCEEDED
