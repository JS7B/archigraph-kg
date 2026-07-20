"""会话图谱读写：Conversation/Message 节点的 CRUD 与原子整轮追加。"""

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
SET cv.turn_counter = $turn_index,
    cv.message_count = cv.message_count + 1
RETURN m.message_id AS message_id, m.conversation_id AS conversation_id,
       m.turn_index AS turn_index, m.role AS role, m.text AS text,
       m.citations AS citations, m.confidence AS confidence, m.created_at AS created_at
"""

# 真实递增的内部属性确保 Neo4j 获取 Conversation 的写锁，并把锁持有到 managed
# transaction 提交。不能用把属性 SET 成原值的 no-op 充当锁。
_LOCK_CONVERSATION = """
MATCH (cv:Conversation {conversation_id: $conversation_id})
SET cv._turn_lock = coalesce(cv._turn_lock, 0) + 1,
    cv.message_count = coalesce(cv.message_count, 0),
    cv.turn_counter = coalesce(cv.turn_counter, cv.message_count, 0)
RETURN cv.turn_counter AS turn_counter
"""

_GET_TURN_BY_RUN = """
MATCH (cv:Conversation {conversation_id: $conversation_id})-[:HAS_MESSAGE]->(m:Message)
WHERE m.run_id = $run_id
RETURN m.message_id AS message_id, m.conversation_id AS conversation_id,
       m.turn_index AS turn_index, m.role AS role, m.text AS text,
       m.citations AS citations, m.confidence AS confidence, m.created_at AS created_at
ORDER BY m.turn_index ASC
"""

_CREATE_TURN = """
MATCH (cv:Conversation {conversation_id: $conversation_id})
CREATE (user_message:Message {
  message_id: $user_message_id,
  conversation_id: $conversation_id,
  run_id: $run_id,
  turn_index: $user_turn_index,
  role: 'user',
  text: $user_text,
  citations: $user_citations,
  confidence: $user_confidence,
  embedding: $user_embedding,
  created_at: $created_at
})
CREATE (agent_message:Message {
  message_id: $agent_message_id,
  conversation_id: $conversation_id,
  run_id: $run_id,
  turn_index: $agent_turn_index,
  role: 'agent',
  text: $agent_text,
  citations: $agent_citations,
  confidence: $agent_confidence,
  embedding: $agent_embedding,
  created_at: $created_at
})
CREATE (cv)-[:HAS_MESSAGE]->(user_message)
CREATE (cv)-[:HAS_MESSAGE]->(agent_message)
SET cv.turn_counter = $agent_turn_index,
    cv.message_count = cv.message_count + 2
WITH user_message, agent_message
UNWIND [user_message, agent_message] AS m
RETURN m.message_id AS message_id, m.conversation_id AS conversation_id,
       m.turn_index AS turn_index, m.role AS role, m.text AS text,
       m.citations AS citations, m.confidence AS confidence, m.created_at AS created_at
ORDER BY m.turn_index ASC
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


class ConversationNotFound(LookupError):
    """Raised when a turn cannot be appended because its Conversation is gone."""


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
    """Compatibility helper for single-message fixtures; production uses append_turn."""

    def _write(tx):
        lock_record = tx.run(
            _LOCK_CONVERSATION, conversation_id=conversation_id
        ).single()
        if lock_record is None:
            raise ConversationNotFound(conversation_id)
        turn_index = lock_record["turn_counter"] + 1
        record = tx.run(
            _ADD_MESSAGE,
            conversation_id=conversation_id,
            message_id=f"{conversation_id}#{turn_index}",
            turn_index=turn_index,
            role=role,
            text=text,
            citations=(
                json.dumps([c.model_dump(by_alias=True) for c in citations])
                if citations
                else None
            ),
            confidence=confidence,
            embedding=embedding,
            created_at=int(time.time() * 1000),
        ).single()
        return _row_to_message(record.data())

    with driver.session(database=database) as session:
        return session.execute_write(_write)


def _turn_message_id(conversation_id: str, run_id: str, role: str) -> str:
    """Build a deterministic opaque id so transaction retries cannot duplicate nodes."""
    value = uuid.uuid5(
        uuid.NAMESPACE_URL, f"archigraph:{conversation_id}:{run_id}:{role}"
    )
    return f"msg_{value.hex}"


def _validate_complete_turn(messages: list[Message], run_id: str) -> tuple[Message, Message]:
    """Reject malformed idempotency state instead of overwriting a partial prior turn."""
    if len(messages) != 2:
        raise RuntimeError(f"run {run_id} has an incomplete persisted turn")
    user, agent = messages
    if (
        user.role != "user"
        or agent.role != "agent"
        or agent.turn_index != user.turn_index + 1
    ):
        raise RuntimeError(f"run {run_id} has a malformed persisted turn")
    return user, agent


def _append_turn_tx(
    tx,
    *,
    conversation_id: str,
    run_id: str,
    user_text: str,
    agent_text: str,
    user_embedding: list[float],
    agent_embedding: list[float],
    citations: list[Citation],
    confidence: str | None,
    created_at: int,
) -> tuple[Message, Message]:
    lock_record = tx.run(
        _LOCK_CONVERSATION, conversation_id=conversation_id
    ).single()
    if lock_record is None:
        raise ConversationNotFound(conversation_id)

    existing = [
        _row_to_message(record.data())
        for record in tx.run(
            _GET_TURN_BY_RUN,
            conversation_id=conversation_id,
            run_id=run_id,
        )
    ]
    if existing:
        return _validate_complete_turn(existing, run_id)

    user_turn_index = lock_record["turn_counter"] + 1
    agent_turn_index = user_turn_index + 1
    records = tx.run(
        _CREATE_TURN,
        conversation_id=conversation_id,
        run_id=run_id,
        user_message_id=_turn_message_id(conversation_id, run_id, "user"),
        agent_message_id=_turn_message_id(conversation_id, run_id, "agent"),
        user_turn_index=user_turn_index,
        agent_turn_index=agent_turn_index,
        user_text=user_text,
        agent_text=agent_text,
        user_citations=None,
        agent_citations=(
            json.dumps([citation.model_dump(by_alias=True) for citation in citations])
            if citations
            else None
        ),
        user_confidence=None,
        agent_confidence=confidence,
        user_embedding=user_embedding,
        agent_embedding=agent_embedding,
        created_at=created_at,
    )
    return _validate_complete_turn(
        [_row_to_message(record.data()) for record in records], run_id
    )


def append_turn(
    driver: Driver,
    conversation_id: str,
    *,
    run_id: str,
    user_text: str,
    agent_text: str,
    user_embedding: list[float],
    agent_embedding: list[float],
    citations: list[Citation] | None = None,
    confidence: str | None = None,
    database: str = "neo4j",
) -> tuple[Message, Message]:
    """Atomically append one user/agent pair, idempotently keyed by ``run_id``."""
    with driver.session(database=database) as session:
        return session.execute_write(
            _append_turn_tx,
            conversation_id=conversation_id,
            run_id=run_id,
            user_text=user_text,
            agent_text=agent_text,
            user_embedding=user_embedding,
            agent_embedding=agent_embedding,
            citations=citations or [],
            confidence=confidence,
            created_at=int(time.time() * 1000),
        )


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
