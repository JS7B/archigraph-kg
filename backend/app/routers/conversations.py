"""会话 CRUD 路由：多轮对话记忆的会话管理（列表/新建/详情/改名/删除）。

响应用 camelCase alias（by_alias=True），与 chat 路由风格一致。删除走同步模式
（清单 §2.2，会话删除较轻），返回 {deleted:true}。
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from app.conversations import (
    create_conversation,
    delete_conversation,
    get_conversation,
    get_messages,
    list_conversations,
    rename_conversation,
)
from app.qa.models import Citation

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


class CreateConversationRequest(BaseModel):
    title: str | None = None


class RenameConversationRequest(BaseModel):
    title: str


class ConversationItem(BaseModel):
    """会话列表项。"""

    model_config = ConfigDict(populate_by_name=True)

    conversation_id: str = Field(alias="conversationId")
    title: str
    created_at: int = Field(alias="createdAt")
    message_count: int = Field(alias="messageCount")


class MessageItem(BaseModel):
    """单条消息（会话详情内）。"""

    model_config = ConfigDict(populate_by_name=True)

    message_id: str = Field(alias="messageId")
    turn_index: int = Field(alias="turnIndex")
    role: str
    text: str
    confidence: str | None = None
    citations: list[Citation] = Field(default_factory=list)


class ConversationDetail(BaseModel):
    """会话详情（含全部消息）。"""

    model_config = ConfigDict(populate_by_name=True)

    conversation_id: str = Field(alias="conversationId")
    title: str
    created_at: int = Field(alias="createdAt")
    message_count: int = Field(alias="messageCount")
    messages: list[MessageItem] = Field(default_factory=list)


@router.get("")
async def list_conversations_endpoint(request: Request) -> dict:
    """会话列表（按 createdAt 降序）。"""
    driver = request.app.state.neo4j
    convs = list_conversations(driver)
    return {
        "items": [
            ConversationItem(
                conversation_id=c.conversation_id,
                title=c.title,
                created_at=c.created_at,
                message_count=c.message_count,
            ).model_dump(by_alias=True)
            for c in convs
        ]
    }


@router.post("")
async def create_conversation_endpoint(
    request: Request, body: CreateConversationRequest | None = None
) -> dict:
    """新建空会话（title 缺省为"新会话"）。返回单会话结构（messages=[]）。"""
    driver = request.app.state.neo4j
    title = (body.title if body and body.title else None) or "新会话"
    conv = create_conversation(driver, title=title)
    return ConversationDetail(
        conversation_id=conv.conversation_id,
        title=conv.title,
        created_at=conv.created_at,
        message_count=0,
        messages=[],
    ).model_dump(by_alias=True)


@router.get("/{conversation_id}")
async def get_conversation_endpoint(request: Request, conversation_id: str) -> dict:
    """单会话详情 + 全部消息（按 turnIndex 升序）。"""
    driver = request.app.state.neo4j
    conv = get_conversation(driver, conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail=f"会话不存在: {conversation_id}")
    messages = get_messages(driver, conversation_id)
    return ConversationDetail(
        conversation_id=conv.conversation_id,
        title=conv.title,
        created_at=conv.created_at,
        message_count=conv.message_count,
        messages=[
            MessageItem(
                message_id=m.message_id,
                turn_index=m.turn_index,
                role=m.role,
                text=m.text,
                confidence=m.confidence,
                citations=m.citations,
            )
            for m in messages
        ],
    ).model_dump(by_alias=True)


@router.patch("/{conversation_id}")
async def rename_conversation_endpoint(
    request: Request, conversation_id: str, body: RenameConversationRequest
) -> dict:
    """改会话标题。空白标题 422，会话不存在 404，成功返回更新后的会话项。"""
    driver = request.app.state.neo4j
    title = body.title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="标题不能为空")
    conv = rename_conversation(driver, conversation_id, title)
    if conv is None:
        raise HTTPException(status_code=404, detail=f"会话不存在: {conversation_id}")
    return ConversationItem(
        conversation_id=conv.conversation_id,
        title=conv.title,
        created_at=conv.created_at,
        message_count=conv.message_count,
    ).model_dump(by_alias=True)


@router.delete("/{conversation_id}")
async def delete_conversation_endpoint(request: Request, conversation_id: str) -> dict:
    """同步删除会话及其全部消息。不存在返回 404。"""
    driver = request.app.state.neo4j
    deleted = delete_conversation(driver, conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"会话不存在: {conversation_id}")
    return {"deleted": True}
