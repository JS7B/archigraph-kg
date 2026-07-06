"""问答路由：POST /api/chat 生成带引用答案；GET /api/chunks/{id} 反查引用原文。

响应用 model_dump(by_alias=True) 输出前端期望的 camelCase。
"""

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from app.conversations import (
    DEFAULT_TITLE,
    create_conversation,
    get_conversation,
    rename_conversation,
)
from app.runs.models import RunKind
from app.runs.tasks import run_chat

router = APIRouter(prefix="/api", tags=["qa"])

# 会话标题最长字数（首句提问截断）
_TITLE_MAX_LEN = 20


def _derive_title(question: str) -> str:
    """从首句提问派生会话标题：压缩空白后截断 20 字，空问题回退缺省标题。"""
    compact = " ".join(question.split())
    return compact[:_TITLE_MAX_LEN] or DEFAULT_TITLE


class ChatRequest(BaseModel):
    """问答请求。conversationId 可空：null=首问（后端建会话），非空=追问。"""

    model_config = ConfigDict(populate_by_name=True)

    question: str
    conversation_id: str | None = Field(default=None, alias="conversationId")


class ChatResponse(BaseModel):
    """异步问答响应：立即返回 runId + conversationId，前端订阅 SSE 终态事件拿 answer。"""

    model_config = ConfigDict(populate_by_name=True)

    run_id: str = Field(alias="runId")
    conversation_id: str = Field(alias="conversationId")


_CHUNK_QUERY = """
MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk {chunk_id: $chunk_id})
RETURN c.chunk_id AS chunk_id, d.source_path AS document_name,
       c.page AS page, c.char_start AS char_start, c.char_end AS char_end,
       c.heading_path AS heading_path, c.text AS text
"""


@router.post("/chat")
async def chat(
    request: Request, background_tasks: BackgroundTasks, body: ChatRequest
) -> dict:
    """对问题起异步 GraphRAG 检索任务（多轮记忆版）。

    conversation_id 同步解析：首问（None）新建会话、追问透传，保证 HTTP 响应能立即
    返回 id（前端拿它后续追问回传）。立即返回 runId + conversationId，前端订阅 SSE 终态事件拿 answer。
    """
    store = request.app.state.runs
    driver = request.app.state.neo4j
    # 同步解析会话 id（避免异步任务未跑完前端拿不到 id）
    conversation_id = body.conversation_id
    if conversation_id is None:
        conversation = create_conversation(driver, title=_derive_title(body.question))
        conversation_id = conversation.conversation_id
    else:
        # 「新建」按钮建的空会话仍是缺省标题：首问时用问题命名（手动改过名则不覆盖）
        conversation = get_conversation(driver, conversation_id)
        if (
            conversation is not None
            and conversation.message_count == 0
            and conversation.title == DEFAULT_TITLE
        ):
            rename_conversation(driver, conversation_id, _derive_title(body.question))
    run = store.create_run(RunKind.CHAT)
    background_tasks.add_task(
        run_chat, driver, store, run.id, body.question, conversation_id
    )
    return ChatResponse(
        run_id=run.id, conversation_id=conversation_id
    ).model_dump(by_alias=True)


@router.get("/chunks/{chunk_id}")
async def get_chunk(request: Request, chunk_id: str) -> dict:
    """按 chunk_id 反查原文，供前端展开引用。"""
    driver = request.app.state.neo4j
    records, _, _ = driver.execute_query(
        _CHUNK_QUERY, chunk_id=chunk_id, database_="neo4j"
    )
    if not records:
        raise HTTPException(status_code=404, detail=f"chunk 不存在: {chunk_id}")
    r = records[0]
    location_parts = []
    if r["page"] is not None:
        location_parts.append(f"第{r['page']}页")
    if r["heading_path"]:
        location_parts.append(" > ".join(r["heading_path"]))
    location_parts.append(f"字符 {r['char_start']}-{r['char_end']}")
    return {
        "chunkId": r["chunk_id"],
        "documentName": r["document_name"],
        "location": " · ".join(location_parts),
        "text": r["text"],
    }
