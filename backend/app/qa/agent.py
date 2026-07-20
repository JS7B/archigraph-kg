"""Agentic RAG：ReAct 检索-反思循环 + function calling。

与 pipeline.answer_question（固定线性 embed→召回→rerank→扩展→生成）的区别：
LLM 自主决定检索什么查询、何时挖关系、证据够不够——不够就换查询再检索。
用 OpenAI 原生 function calling（tools 字段），自研轻量 while 循环，零新依赖，
编排控制权留在项目内（不引 LangGraph/LangChain）。

循环终止两条路径：①模型返回无 tool_calls（认为证据足够）→ 生成答案；
②达到 max_turns 硬上限 → 强制生成兜底答案。两种都走同一答案生成分支，
引用仍走 build_context 的 [n]↔Citation 闭环，引用可追溯红线不退化。
"""

import json
import logging
import re
from typing import Callable

from neo4j import Driver
from openai import BadRequestError
from pydantic import BaseModel

from app.clients import llm
from app.graph.search import ChunkHit, search_chunks
from app.qa.context import build_context
from app.qa.expand import expand_entities
from app.qa.models import Answer, Citation, RelationPath
from app.qa.prompt import build_answer_messages
from app.qa.rerank import rerank_chunks
from app.runs.models import Stage

logger = logging.getLogger(__name__)

# 证据裁剪：工具结果只回 chunk_id + 正文前 N 字，控 token、不塞整段反复留历史。
_SNIPPET_LEN = 200


class ToolCallingUnsupported(RuntimeError):
    """LLM 端点不支持 function calling（BadRequestError），agent 无法运行。

    由 run_chat 捕获后回退线性 answer_question，保证问答不挂。
    """


# ── Agent system prompt：教模型何时用哪个工具、何时停止 ──

_AGENT_SYSTEM_PROMPT = (
    "你是严谨的知识库问答助手。你可以调用工具检索知识库，自主决定检索策略。\n"
    "工具：\n"
    "- vector_search(query)：按关键词检索相关文档片段。需要具体事实、技术细节、文档内容时用。\n"
    "- expand_entity(chunk_ids)：根据已检索到的片段，沿实体关系图谱扩展，挖掘片段间的关联。\n"
    "工作方式（ReAct）：\n"
    "1. 先判断是否需要检索——能直接答的简单问题可不调工具。\n"
    "2. 需要证据时，用 vector_search 检索；拿到片段后评估是否足够回答。\n"
    "3. 若证据不足或需要补充关联信息，可换一个查询再检索，或用 expand_entity 挖关系。\n"
    "4. 当证据足以回答时，停止调用工具，直接给出最终答案。\n"
    "回答规则：每条来自文档的论断，在句末用方括号角标标注来源，如 [1]、[2]，"
    "角标号对应检索结果里的片段编号。若检索不到足够信息，说明「根据现有资料无法回答」，不要编造。\n"
    "注意：上方可能有同会话的对话历史作为上下文参考，但回答仍须基于本次检索到的【文档片段】"
    "并用 [n] 角标标注引用，不得仅凭历史记忆作答。"
)


# ── 工具定义（OpenAI function calling JSON Schema）──

_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "vector_search",
            "description": (
                "按关键词检索知识库，返回最相关的文档片段（含编号、id、正文摘要）。"
                "需要查找事实、技术细节、文档内容时调用。可多次调用不同查询。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "检索关键词或自然语言问题",
                    }
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "expand_entity",
            "description": (
                "根据已检索到的文档片段 id，沿实体关系图谱扩展，返回片段涉及的实体间的关联关系。"
                "已检索到片段、想了解概念之间的联系时调用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "chunk_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "已检索到的文档片段 id 列表",
                    }
                },
                "required": ["chunk_ids"],
                "additionalProperties": False,
            },
        },
    },
]


def _assistant_msg_to_dict(msg) -> dict:
    """把 SDK 的 ChatCompletionMessage 转成可入 messages 历史的 dict。

    含 tool_calls 时必须保留，否则下一轮模型会因找不到对应 tool result 而报错。
    """
    d: dict = {"role": "assistant", "content": msg.content or ""}
    if msg.tool_calls:
        d["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in msg.tool_calls
        ]
    return d


def _run_vector_search(
    driver: Driver, query: str, *, top_k: int, rerank_top_n: int, database: str
) -> list[ChunkHit]:
    """vector_search 工具实现：embed → 向量召回 → rerank。"""
    embedding = llm.embed([query])[0]
    hits = search_chunks(driver, embedding, top_k=top_k, database=database)
    return rerank_chunks(query, hits, top_n=rerank_top_n)


def _chunks_to_tool_text(chunks: list[ChunkHit]) -> str:
    """把检索结果裁剪成给模型的文本：编号 + id + 正文前 N 字。控 token。"""
    lines = []
    for i, c in enumerate(chunks, start=1):
        lines.append(f"[{i}] id={c.chunk_id}\n{c.text[:_SNIPPET_LEN]}")
    return "\n\n".join(lines) if lines else "未检索到相关片段。"


def _dispatch_tool(
    name: str,
    arguments: dict,
    driver: Driver,
    *,
    top_k: int,
    rerank_top_n: int,
    database: str,
    evidence_pool: dict[str, ChunkHit],
    paths_acc: list[RelationPath],
) -> str:
    """执行单个工具调用，结果回传给模型（文本）；副作用：累积证据池与关系路径。

    工具失败不抛——回传错误字符串让模型自行决策（handoff 硬规则）。
    """
    try:
        if name == "vector_search":
            query = arguments["query"]
            chunks = _run_vector_search(
                driver, query, top_k=top_k, rerank_top_n=rerank_top_n, database=database
            )
            for c in chunks:
                evidence_pool[c.chunk_id] = c  # 去重累积，保留 provenance
            return _chunks_to_tool_text(chunks)
        if name == "expand_entity":
            chunk_ids = arguments["chunk_ids"]
            ctx = expand_entities(driver, chunk_ids, database=database)
            # 去重累积关系路径（按四元组判重）
            existing = {(p.source_name, p.target_name, p.type, p.evidence_chunk_id) for p in paths_acc}
            for p in ctx.paths:
                key = (p.source_name, p.target_name, p.type, p.evidence_chunk_id)
                if key not in existing:
                    paths_acc.append(p)
                    existing.add(key)
            if not ctx.paths:
                return "未找到这些片段涉及的实体关系。"
            return "\n".join(f"{p.source_name} -[{p.type}]-> {p.target_name}" for p in ctx.paths)
        return f"未知工具: {name}"
    except Exception as exc:  # noqa: BLE001 — 工具失败回传错误，不中断循环
        logger.warning("工具 %s 执行失败：%s", name, exc)
        return f"工具 {name} 执行失败: {exc}"


def _tool_stage(name: str) -> tuple[Stage, str]:
    """工具名 → (RunEvent stage, message)，驱动前端像素动画按工具类型走。"""
    if name == "vector_search":
        return Stage.SEARCHING, "向量检索"
    if name == "expand_entity":
        return Stage.LINKING, "扩展实体关系"
    return Stage.CHECKING, "处理工具结果"


def _generate_final_answer(
    driver: Driver,
    question: str,
    evidence_pool: dict[str, ChunkHit],
    paths_acc: list[RelationPath],
    *,
    retrieval_question: str | None = None,
    history: list[dict] | None = None,
    on_event: Callable[..., None] | None = None,
) -> Answer:
    """用证据池去重后的 chunks 生成带引用的最终答案。复用 build_context + prompt 闭环。"""
    if on_event:
        on_event(Stage.WRITING, "生成带引用回答")
    chunks = list(evidence_pool.values())
    if not chunks:
        return Answer(text="根据现有资料无法回答。", confidence="low", citations=[])
    context_str, citations = build_context(chunks, paths_acc)
    text = llm.chat(
        build_answer_messages(
            question,
            context_str,
            history=history,
            retrieval_question=retrieval_question,
        )
    )
    used = {int(n) for n in re.findall(r"\[(\d+)\]", text)}
    cited = [c for c in citations if c.index in used] if used else []
    confidence = "high" if len(used) >= 2 else ("medium" if used else "low")
    return Answer(text=text, confidence=confidence, citations=cited)


def answer_question_agentic(
    driver: Driver,
    question: str,
    *,
    max_turns: int = 4,
    top_k: int = 10,
    rerank_top_n: int = 5,
    database: str = "neo4j",
    history: list[dict] | None = None,
    retrieval_question: str | None = None,
    on_event: Callable[..., None] | None = None,
) -> Answer:
    """Agentic RAG 问答：ReAct 循环，LLM 自主决定检索策略，证据足够后生成带引用答案。

    history 为同会话近期对话（已规整为 {role,content} 列表），插入到 system 与当前
    检索问题之间。retrieval_question 是上层只生成一次的独立检索问题；未传时仍使用
    原始 question，保持单轮调用兼容。最终生成始终以 question 的原始语义为准。
    on_event 回调让循环每一步通知外部（run_chat 用它 emit RunEvent），本函数不依赖
    RunStore，保持纯检索逻辑、可单测。端点不支持 tool calling 时抛 ToolCallingUnsupported。
    """
    evidence_pool: dict[str, ChunkHit] = {}
    paths_acc: list[RelationPath] = []
    planning_question = retrieval_question or question
    messages: list[dict] = [{"role": "system", "content": _AGENT_SYSTEM_PROMPT}]
    if history:
        messages.extend(history)  # 追问上下文：system 之后、当前问题之前
    messages.append({"role": "user", "content": planning_question})


    for turn in range(max_turns):
        try:
            msg = llm.chat_with_tools(messages, tools=_TOOLS, tool_choice="auto")
        except BadRequestError as exc:
            # 端点不支持 tools 的典型表现；上抛让 run_chat 降级到线性 pipeline。
            raise ToolCallingUnsupported(str(exc)) from exc
        logger.debug("agent turn %d response: tool_calls=%s content=%s",
                     turn, [tc.function.name for tc in (msg.tool_calls or [])],
                     (msg.content or "")[:200])

        messages.append(_assistant_msg_to_dict(msg))

        tool_calls = msg.tool_calls or []
        if not tool_calls:
            # 模型认为证据足够（或能直接答），生成最终答案
            if on_event:
                on_event(Stage.CHECKING, "评估证据充分性")
            return _generate_final_answer(
                driver,
                question,
                evidence_pool,
                paths_acc,
                retrieval_question=retrieval_question,
                history=history,
                on_event=on_event,
            )

        # 遍历执行本轮所有 tool_calls（OpenAI 可并行返回多个，必须全执行全回传）
        for tc in tool_calls:
            tool_name = tc.function.name
            try:
                arguments = json.loads(tc.function.arguments)
            except (json.JSONDecodeError, TypeError):
                arguments = {}  # 防幻觉参数，回传错误让模型纠正
                tool_result = f"参数解析失败: {tc.function.arguments}"
            else:
                stage, message = _tool_stage(tool_name)
                tool_result = _dispatch_tool(
                    tool_name,
                    arguments,
                    driver,
                    top_k=top_k,
                    rerank_top_n=rerank_top_n,
                    database=database,
                    evidence_pool=evidence_pool,
                    paths_acc=paths_acc,
                )
                # B12：工具调用事件携带结构化可观测字段
                if on_event:
                    on_event(
                        stage, message,
                        tool_name=tool_name,
                        tool_input=arguments,
                        tool_output=tool_result[:500],  # 裁剪防过长
                    )
            messages.append(
                {"role": "tool", "tool_call_id": tc.id, "content": tool_result}
            )

    # 达 max_turns 硬上限，强制用已有证据生成兜底答案
    logger.info("agent 达 max_turns=%d，强制生成兜底答案", max_turns)
    return _generate_final_answer(
        driver,
        question,
        evidence_pool,
        paths_acc,
        retrieval_question=retrieval_question,
        history=history,
        on_event=on_event,
    )
