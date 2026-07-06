"""会话图谱读写：Conversation/Message 节点的 CRUD。

函数均接收 driver，关键字段走参数。message_id 确定性（conv_id#turn_index）保证幂等：
重复写同消息（如任务重试）MERGE 不翻倍。turn_index 自动算（max+1）。

add_message 用两段 Cypher：先算 next_turn，再用确定的 message_id MERGE——因为
message_id 依赖 turn_index，而 turn_index 在 MERGE 时才确定，必须先算出来才能
保证 message_id 确定性（幂等可重试的前提）。
"""

import json
import time
import uuid

from neo4j import Driver

from app.conversations.models import Conversation, Message
from app.qa.models import Citation

# 新建会话的缺省标题；首问时若仍是它则用问题改名（见 routers/chat.py）。
DEFAULT_TITLE = "新会话"

_CREATE = """
MERGE (cv:Conversation {conversation_id: $conversation_id})
  SET cv.title = $title,
      cv.created_at = $created_at,
      cv.message_count = 0
RETURN cv.conversation_id AS conversation_id, cv.title AS title,
       cv.created_at AS created_at, cv.message_count AS message_count
"""

_NEXT_TURN = """
MATCH (cv:Conversation {conversation_id: $conversation_id})
OPTIONAL MATCH (cv)-[:HAS_MESSAGE]->(existing:Message)
RETURN coalesce(max(existing.turn_index), 0) + 1 AS next_turn
"""

_ADD_MESSAGE = """
MATCH (cv:Conversation {conversation_id: $conversation_id})
MERGE (m:Message {message_id: $message_id})
  SET m.conversation_id = $conversation_id,
      m.turn_index = $turn_index,
      m.role = $role,
      m.text = $text,
      m.citations = $citations,
      m.confidence = $confidence,
      m.embedding = $embedding,
      m.created_at = $created_at
MERGE (cv)-[:HAS_MESSAGE]->(m)
WITH cv, m
SET cv.message_count = count { (cv)-[:HAS_MESSAGE]->(:Message) }
RETURN m.message_id AS message_id, m.conversation_id AS conversation_id,
       m.turn_index AS turn_index, m.role AS role, m.text AS text,
       m.citations AS citations, m.confidence AS confidence, m.created_at AS created_at
"""

_GET_MESSAGES = """
MATCH (m:Message {conversation_id: $conversation_id})
RETURN m.message_id AS message_id, m.conversation_id AS conversation_id,
       m.turn_index AS turn_index, m.role AS role, m.text AS text,
       m.citations AS citations, m.confidence AS confidence, m.created_at AS created_at
ORDER BY m.turn_index ASC
"""

_LIST_CONVERSATIONS = """
MATCH (cv:Conversation)
RETURN cv.conversation_id AS conversation_id, cv.title AS title,
       cv.created_at AS created_at, cv.message_count AS message_count
ORDER BY cv.created_at DESC
"""

_GET_CONVERSATION = """
MATCH (cv:Conversation {conversation_id: $conversation_id})
RETURN cv.conversation_id AS conversation_id, cv.title AS title,
       cv.created_at AS created_at, cv.message_count AS message_count
"""

_RENAME = """
MATCH (cv:Conversation {conversation_id: $conversation_id})
SET cv.title = $title
RETURN cv.conversation_id AS conversation_id, cv.title AS title,
       cv.created_at AS created_at, cv.message_count AS message_count
"""

_DELETE = """
MATCH (cv:Conversation {conversation_id: $conversation_id})
OPTIONAL MATCH (cv)-[:HAS_MESSAGE]->(m:Message)
DETACH DELETE m, cv
RETURN count(cv) AS deleted
"""


def _row_to_message(row: dict) -> Message:
    """图谱行 → Message；citations 从 JSON 字符串还原为 list[Citation]。"""
    citations_raw = row.get("citations")
    citations = (
        [Citation.model_validate(c) for c in json.loads(citations_raw)]
        if citations_raw
        else []
    )
    return Message(
        message_id=row["message_id"],
        conversation_id=row["conversation_id"],
        turn_index=row["turn_index"],
        role=row["role"],
        text=row["text"],
        citations=citations,
        confidence=row.get("confidence"),
        created_at=row["created_at"],
    )


def create_conversation(
    driver: Driver, *, title: str = DEFAULT_TITLE, database: str = "neo4j"
) -> Conversation:
    """新建会话，返回 Conversation。conversation_id 用 conv_ 前缀 + 12 位 hex。"""
    conversation_id = f"conv_{uuid.uuid4().hex[:12]}"
    records, _, _ = driver.execute_query(
        _CREATE,
        conversation_id=conversation_id,
        title=title,
        created_at=int(time.time() * 1000),
        database_=database,
    )
    return Conversation(**records[0].data())


def add_message(
    driver: Driver,
    conversation_id: str,
    *,
    role: str,
    text: str,
    embedding: list[float],
    citations: list[Citation] | None = None,
    confidence: str | None = None,
    database: str = "neo4j",
) -> Message:
    """向会话追加一条消息，自动算 turn_index，幂等 MERGE by message_id。"""
    # 第一步：算 next_turn（保证 message_id 确定性，幂等可重试的前提）
    turn_records, _, _ = driver.execute_query(
        _NEXT_TURN, conversation_id=conversation_id, database_=database
    )
    next_turn = turn_records[0]["next_turn"]
    message_id = f"{conversation_id}#{next_turn}"

    # 第二步：用确定的 message_id MERGE（重复写同消息不翻倍）
    records, _, _ = driver.execute_query(
        _ADD_MESSAGE,
        conversation_id=conversation_id,
        message_id=message_id,
        turn_index=next_turn,
        role=role,
        text=text,
        citations=json.dumps([c.model_dump(by_alias=True) for c in citations]) if citations else None,
        confidence=confidence,
        embedding=embedding,
        created_at=int(time.time() * 1000),
        database_=database,
    )
    return _row_to_message(records[0].data())


def get_messages(
    driver: Driver, conversation_id: str, *, limit: int | None = None, database: str = "neo4j"
) -> list[Message]:
    """按 turn_index 升序返回会话消息；limit 实现「注入窗口」（None=全量）。"""
    records, _, _ = driver.execute_query(
        _GET_MESSAGES, conversation_id=conversation_id, database_=database
    )
    messages = [_row_to_message(r.data()) for r in records]
    return messages[-limit:] if limit else messages


def list_conversations(driver: Driver, *, database: str = "neo4j") -> list[Conversation]:
    """按 created_at 降序返回所有会话。"""
    records, _, _ = driver.execute_query(_LIST_CONVERSATIONS, database_=database)
    return [Conversation(**r.data()) for r in records]


def get_conversation(
    driver: Driver, conversation_id: str, *, database: str = "neo4j"
) -> Conversation | None:
    """取单个会话，不存在返回 None。"""
    records, _, _ = driver.execute_query(
        _GET_CONVERSATION, conversation_id=conversation_id, database_=database
    )
    return Conversation(**records[0].data()) if records else None


def rename_conversation(
    driver: Driver, conversation_id: str, title: str, *, database: str = "neo4j"
) -> Conversation | None:
    """改会话标题，返回更新后的 Conversation；会话不存在返回 None。"""
    records, _, _ = driver.execute_query(
        _RENAME, conversation_id=conversation_id, title=title, database_=database
    )
    return Conversation(**records[0].data()) if records else None


def delete_conversation(driver: Driver, conversation_id: str, *, database: str = "neo4j") -> bool:
    """DETACH DELETE 消息 + 会话。返回是否删除了会话（True=存在并已删）。"""
    records, _, _ = driver.execute_query(
        _DELETE, conversation_id=conversation_id, database_=database
    )
    return records[0]["deleted"] > 0
