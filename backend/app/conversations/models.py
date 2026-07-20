"""会话与消息数据模型（多轮对话记忆）。

复用 qa.models 的 _CamelModel（camelCase alias 基类），对外响应字段统一 camelCase。
Message.citations 内部存 list[Citation]，写入图谱时 json.dumps，读出时 json.loads。
"""

import time

from pydantic import Field

from app.qa.models import Citation, _CamelModel


class Conversation(_CamelModel):
    """一个会话：固定元数据。message_count 由 add_message 维护。"""

    conversation_id: str
    title: str = "新会话"
    created_at: int = Field(default_factory=lambda: int(time.time() * 1000))
    message_count: int = 0


class Message(_CamelModel):
    """一条对话消息（user 或 agent）。

    citations / confidence 仅 agent 消息携带，user 消息为空列表 / None。
    message_id 是对外不透明标识；调用方不得从它推断 turn_index。turn_index 从 1 起。
    """

    message_id: str
    conversation_id: str
    turn_index: int
    role: str  # "user" | "agent"
    text: str
    citations: list[Citation] = Field(default_factory=list)
    confidence: str | None = None  # high/medium/low（agent）；user 为 None
    created_at: int = Field(default_factory=lambda: int(time.time() * 1000))
