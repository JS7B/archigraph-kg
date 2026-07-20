"""后台任务：把入库/问答/删除的同步链路包成「带进度事件」的异步执行单元。

BackgroundTasks 在事件循环线程跑，但入库/问答的同步阻塞调用（parse/embed/llm/
execute_query）会独占事件循环——导致 SSE 推送冻结、前端进度条卡住、像素动画实时性
失效。故把阻塞段用 asyncio.to_thread 丢到线程池，让事件循环空闲时能即时推送 SSE。

跨线程 emit 处理（关键）：run_chat 把 answer_question_agentic 整个包进 to_thread，
agent 在工作线程内通过 on_event 回调 emit 事件。RunStore（dict/asyncio.Queue）非
线程安全，工作线程不能直接调 store.append_event。用 loop.call_soon_threadsafe 把
emit 操作投递回事件循环线程执行，保证 RunStore 只在单线程访问。

每个任务全程 try/except：BackgroundTasks 会吞掉异常，失败必须自己 emit error +
run.status=failed，否则前端 SSE 流永不关闭、像素 Agent 卡在中间状态。
"""

import asyncio
import logging
import os
import tempfile

from neo4j import Driver

from app.clients import llm
from app.conversations import (
    append_turn,
    create_conversation,
    get_messages,
)
from app.extraction import extract_and_ingest
from app.graph import embed_chunks, ingest_document
from app.graph.embedding import embed_texts
from app.parsing import parse_file
from app.qa.agent import ToolCallingUnsupported, answer_question_agentic
from app.qa.pipeline import answer_question
from app.qa.question_rewrite import resolve_retrieval_question
from app.runs.models import RunEvent, RunStatus, Stage
from app.runs.store import RunStore

logger = logging.getLogger(__name__)

# LLM 并发上限（B14）：个人单用户场景，3 足够防并发打爆 rate limit。
# Python 3.10+ 的 asyncio.Semaphore 不再绑定具体 loop，模块级创建安全。
_LLM_SEMAPHORE = asyncio.Semaphore(3)

# 多轮对话记忆窗口：注入最近 N 条消息（约 3 组问答），控 token；全量存图谱。
_MAX_HISTORY_TURNS = 6


def _emit(store: RunStore, run_id: str, stage: Stage, status=RunStatus.RUNNING, **kw):
    """记一条进度事件。失败时 status=FAILED，成功终态 status=SUCCEEDED。"""
    store.append_event(run_id, RunEvent(stage=stage, status=status, **kw))


async def run_ingest(
    driver: Driver,
    store: RunStore,
    run_id: str,
    file_bytes: bytes,
    filename: str,
    doc_type: str,
) -> None:
    """入库后台任务：uploading→parsing→indexing(向量)→extracting(逐chunk)→indexing→done。

    document_id 用源文件名，保证 chunk_id 幂等（与 A 板块同步路由一致）。
    注：向量写入在抽取之前（writer 的 MENTIONS 依赖 Chunk 节点已存在），故 indexing
    先出现一次；LLM 抽取按 chunk 逐条发 extracting 进度事件。
    """
    try:
        _emit(store, run_id, Stage.UPLOADING, message=f"接收 {filename}")
        source_name = os.path.basename(filename)

        _emit(store, run_id, Stage.PARSING, message="解析文档")
        # parse_file 需要文件句柄（PDF/Markdown），落临时盘再解析；finally 清理。
        suffix = os.path.splitext(source_name)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, prefix="run_") as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name
        try:
            doc = await asyncio.to_thread(parse_file, tmp_path, document_id=source_name)
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

        _emit(store, run_id, Stage.INDEXING, message="生成向量并写入图库")
        # embed/ingest 是同步阻塞（HTTP/Cypher），包 to_thread 不冻结事件循环。
        # title 必须显式传源文件名：doc.source_path 是临时文件路径，不能当标题前缀。
        embeddings = await asyncio.to_thread(
            lambda: embed_chunks(doc, title=source_name)
        )
        await asyncio.to_thread(
            ingest_document, driver, doc, embeddings, name=source_name, source_type=doc_type
        )

        # 抽取是入库最长的一段（每 chunk 一次 LLM 调用，动辄数分钟）。每完成一个
        # 可抽取 chunk 发进度事件，消除前端"卡死"错觉。回调在 to_thread 工作线程
        # 内触发，RunStore 非线程安全，用 call_soon_threadsafe 投递回事件循环线程。
        loop = asyncio.get_running_loop()

        def _extract_progress(index: int, total: int) -> None:
            event = RunEvent(
                stage=Stage.EXTRACTING,
                message=f"已从分块 {index}/{total} 中抽取实体与关系",
            )
            loop.call_soon_threadsafe(store.append_event, run_id, event)

        stats = await asyncio.to_thread(
            extract_and_ingest, driver, doc, on_progress=_extract_progress
        )

        _emit(store, run_id, Stage.INDEXING, message="实体与关系已写入图谱")
        _emit(
            store, run_id, Stage.IDLE, RunStatus.SUCCEEDED,
            message=(
                f"入库完成：{stats.entity_count} 实体 / "
                f"{stats.relation_count} 关系 / {len(stats.failed_chunks)} 失败 chunk"
            ),
        )
    except Exception as exc:  # noqa: BLE001 — 后台任务必须吞异常并记录
        logger.exception("入库任务失败 run=%s", run_id)
        _emit(store, run_id, Stage.ERROR, RunStatus.FAILED, message=f"入库失败: {exc}")


async def run_chat(
    driver: Driver,
    store: RunStore,
    run_id: str,
    question: str,
    conversation_id: str,
) -> None:
    """问答后台任务（Agentic RAG + 多轮记忆）：通过 on_event 让 Agent 每步真实 emit 事件。

    conversation_id 由 chat 路由同步解析（首问新建、追问透传）后传入，保证 HTTP 响应
    能立即返回 id。本任务读近期历史注入 Agent、调 answer_question_agentic、写回本轮
    两条消息。降级：LLM 端点不支持 function calling 时，回退线性 answer_question（也带历史）。
    """
    try:
        answer = await _run_chat_agentic(driver, store, run_id, question, conversation_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("问答任务失败 run=%s", run_id)
        _emit(store, run_id, Stage.ERROR, RunStatus.FAILED, message=f"回答失败: {exc}")
        return

    _emit(
        store, run_id, Stage.IDLE, RunStatus.SUCCEEDED,
        message=f"回答完成（{len(answer.citations)} 条引用）",
        answer=answer.model_dump(by_alias=True),
    )


def _to_history(messages) -> list[dict]:
    """把图谱 Message 列表规整成 LLM messages 历史（{role,content}）。"""
    role_map = {"user": "user", "agent": "assistant"}
    return [{"role": role_map[m.role], "content": m.text} for m in messages]


async def _run_chat_agentic(
    driver: Driver, store: RunStore, run_id: str, question: str, conversation_id: str
):
    """跑 Agentic RAG + 多轮记忆；端点不支持 tool calling 时降级线性 pipeline。返回 Answer。

    流程：读近期历史 → 一次指代消歧 → 注入 Agent → 调用 → 写回本轮两条消息。
    会话读写是图谱阻塞调用，用 asyncio.to_thread 包裹；on_event 跨线程 emit 用
    call_soon_threadsafe 投递回事件循环线程。
    """
    loop = asyncio.get_running_loop()

    def _emit_cb(stage: Stage, message: str, **extra) -> None:
        event = RunEvent(stage=stage, message=message, **extra)
        loop.call_soon_threadsafe(store.append_event, run_id, event)

    # 读近期历史（注入窗口，控 token）；全量已存图谱
    recent = await asyncio.to_thread(
        get_messages, driver, conversation_id, limit=_MAX_HISTORY_TURNS
    )
    history = _to_history(recent)

    async with _LLM_SEMAPHORE:
        # 重写只在整次 Run 的共享入口执行一次；Agentic 与降级链路复用同一个结果。
        # 无历史传 None，保持既有单轮 planner/final prompt 完全不变。
        retrieval_question = None
        if history:
            retrieval_question = await asyncio.to_thread(
                resolve_retrieval_question, question, history
            )
        try:
            answer = await asyncio.to_thread(
                answer_question_agentic,
                driver,
                question,
                history=history,
                retrieval_question=retrieval_question,
                on_event=_emit_cb,
            )
        except ToolCallingUnsupported as exc:
            logger.warning("LLM 不支持 tool calling，降级线性 RAG：%s", exc)
            _emit(store, run_id, Stage.SEARCHING, message="向量召回 + 重排 + 图谱扩展")
            _emit(store, run_id, Stage.CHECKING, message="组装上下文")
            _emit(store, run_id, Stage.WRITING, message="生成带引用回答")
            answer = await asyncio.to_thread(
                answer_question,
                driver,
                question,
                history=history,
                retrieval_question=retrieval_question,
            )

    # 在开启写事务前一次生成有序的 user/agent embedding；模型调用失败时图中零写入。
    embeddings = await asyncio.to_thread(embed_texts, [question, answer.text])
    await asyncio.to_thread(
        append_turn,
        driver,
        conversation_id,
        run_id=run_id,
        user_text=question,
        agent_text=answer.text,
        user_embedding=embeddings[0],
        agent_embedding=embeddings[1],
        citations=answer.citations, confidence=answer.confidence,
    )
    return answer


async def run_delete(
    driver: Driver,
    store: RunStore,
    run_id: str,
    document_id: str,
) -> None:
    """删除后台任务：deleting→done，清理 Chunk/MENTIONS/RELATES/Entity/Document。

    Entity 的 entity_id 含 document_id（见 extraction/merge.py），按文档隔离、不跨文档共享，
    故删文档时其 Entity 一并按 document_id 清理（比原先靠 MENTIONS 孤立性判定更可靠：
    原写法 NOT (c:Chunk)-[:MENTIONS]->(e) 在 Neo4j 5+ 会因 pattern expression 引入新变量 c 报错）。
    """
    try:
        _emit(store, run_id, Stage.DELETING, message=f"删除 {document_id}")
        await asyncio.to_thread(_do_delete, driver, document_id)
        _emit(store, run_id, Stage.IDLE, RunStatus.SUCCEEDED, message="删除完成")
    except Exception as exc:  # noqa: BLE001
        logger.exception("删除任务失败 run=%s", run_id)
        _emit(store, run_id, Stage.ERROR, RunStatus.FAILED, message=f"删除失败: {exc}")


def _do_delete(driver: Driver, document_id: str) -> None:
    """删除文档全部数据的同步 Cypher：Chunk/Document + 本文档的 Entity。

    一段 Cypher 完成（不拆两段），避免中间状态：第一段成功第二段失败会留下 Document 删了但
    Entity 残留的脏数据。Entity 按 document_id 精确匹配删除（entity_id 含 document_id）。
    """
    driver.execute_query(
        """
        OPTIONAL MATCH (d:Document {document_id: $document_id})
        OPTIONAL MATCH (d)-[:HAS_CHUNK]->(c:Chunk)
        WITH collect(DISTINCT d) AS documents,
             collect(DISTINCT c) AS chunks
        FOREACH (chunk IN chunks | DETACH DELETE chunk)
        FOREACH (document IN documents | DETACH DELETE document)
        WITH 1 AS _
        OPTIONAL MATCH (e:Entity {document_id: $document_id})
        OPTIONAL MATCH (e)-[:RESOLVES_TO]->(affected:CanonicalEntity)
        WITH collect(DISTINCT e) AS entities,
             collect(DISTINCT affected.canonical_id) AS affected_canonical_ids
        FOREACH (entity IN entities | DETACH DELETE entity)
        WITH affected_canonical_ids
        OPTIONAL MATCH (canonical:CanonicalEntity)
        WHERE canonical.canonical_id IN affected_canonical_ids
          AND NOT EXISTS {
          MATCH (:Entity)-[:RESOLVES_TO]->(canonical)
        }
        WITH collect(DISTINCT canonical) AS canonicals
        FOREACH (canonical IN canonicals | DETACH DELETE canonical)
        """,
        document_id=document_id,
        database_="neo4j",
    )
