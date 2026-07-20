"""会话图谱读写测试：create/add/get/list/delete、turn_index 自增、幂等、citations 往返。

复用顶层 conftest 的 ensured_schema（已建 message 索引）+ _clean（清 conv_test 前缀）。
测试用 conv_test 前缀的 conversation_id，自动被 _clean 清理。
"""

from app.conversations import (
    add_message,
    append_turn,
    create_conversation,
    delete_conversation,
    get_conversation,
    get_messages,
    list_conversations,
    rename_conversation,
)
from app.qa.models import Citation

TEST_DIM = 8


def _vec():
    return [1.0] + [0.0] * (TEST_DIM - 1)


def _test_title():
    """生成 conv_test 前缀的标题，保证 _clean 能清理（create_conversation 内部生成 conv_ id）。"""
    return "conv_test_标题"  # 测试通过创建的会话 id 是随机的 conv_xxx，需显式用 conv_test 前缀


def _create_test_conversation(driver, title="测试会话"):
    """创建会话后强制改 conversation_id 为 conv_test 前缀，保证被 _clean 清理。"""
    conv = create_conversation(driver, title=title)
    # 改 id 为 conv_test 前缀（create_conversation 用随机 uuid，测试需可控前缀）
    driver.execute_query(
        "MATCH (cv:Conversation {conversation_id: $old}) "
        "SET cv.conversation_id = $new",
        old=conv.conversation_id,
        new=f"conv_test_{conv.conversation_id[4:]}",  # conv_xxxx → conv_test_xxxx
        database_="neo4j",
    )
    return get_conversation(driver, f"conv_test_{conv.conversation_id[4:]}")


def test_create_conversation(ensured_schema):
    conv = _create_test_conversation(ensured_schema, title="我的会话")
    assert conv.title == "我的会话"
    assert conv.conversation_id.startswith("conv_test_")
    assert conv.message_count == 0
    assert conv.created_at > 0


def test_add_message_turn_index_increments(ensured_schema):
    driver = ensured_schema
    conv = _create_test_conversation(driver)
    m1 = add_message(driver, conv.conversation_id, role="user", text="第一问", embedding=_vec())
    m2 = add_message(driver, conv.conversation_id, role="agent", text="第一答", embedding=_vec())
    assert m1.turn_index == 1
    assert m2.turn_index == 2
    assert m1.message_id == f"{conv.conversation_id}#1"
    assert m2.message_id == f"{conv.conversation_id}#2"


def test_add_message_updates_count(ensured_schema):
    driver = ensured_schema
    conv = _create_test_conversation(driver)
    add_message(driver, conv.conversation_id, role="user", text="问", embedding=_vec())
    add_message(driver, conv.conversation_id, role="agent", text="答", embedding=_vec())
    refreshed = get_conversation(driver, conv.conversation_id)
    assert refreshed.message_count == 2


def test_append_turn_initializes_counter_from_legacy_message_and_is_idempotent(
    ensured_schema,
):
    driver = ensured_schema
    conv = _create_test_conversation(driver)
    add_message(driver, conv.conversation_id, role="user", text="旧问题", embedding=_vec())

    first = append_turn(
        driver,
        conv.conversation_id,
        run_id="run_test_atomic",
        user_text="追问",
        agent_text="回答 [1]",
        user_embedding=_vec(),
        agent_embedding=_vec(),
        citations=[
            Citation(
                index=1,
                chunk_id="c1",
                document_id="d1",
                location="第1页",
                snippet="证据",
            )
        ],
        confidence="high",
    )
    retried = append_turn(
        driver,
        conv.conversation_id,
        run_id="run_test_atomic",
        user_text="不应覆盖",
        agent_text="不应覆盖",
        user_embedding=_vec(),
        agent_embedding=_vec(),
    )

    assert [message.turn_index for message in first] == [2, 3]
    assert [message.message_id for message in retried] == [
        message.message_id for message in first
    ]
    assert [message.text for message in retried] == ["追问", "回答 [1]"]
    assert get_conversation(driver, conv.conversation_id).message_count == 3


def test_add_message_idempotent(ensured_schema):
    """同 message_id 重复 MERGE 不翻倍——幂等硬要求。

    add_message 的 turn_index 是自增的（基于历史长度），故"连续两次 add 相同内容"会
    得到不同 turn_index/message_id（产生两条）。真正的幂等场景是 run_chat 任务重试：
    重试时本轮消息已写入，靠 message_id 相同 MERGE 不翻倍。此处直接用相同 message_id
    验证 MERGE 机制。
    """
    driver = ensured_schema
    conv = _create_test_conversation(driver)
    # 第一次：正常写入，得到 message_id = conv#1
    add_message(driver, conv.conversation_id, role="user", text="问", embedding=_vec())
    # 第二次：手动用相同 message_id + turn_index 再写一遍，验证 MERGE 不翻倍
    driver.execute_query(
        "MATCH (cv:Conversation {conversation_id: $cid}) "
        "MERGE (m:Message {message_id: $mid}) "
        "SET m.turn_index = 1, m.role = 'user', m.text = '问（重试）' "
        "MERGE (cv)-[:HAS_MESSAGE]->(m)",
        cid=conv.conversation_id, mid=f"{conv.conversation_id}#1", database_="neo4j",
    )
    messages = get_messages(driver, conv.conversation_id)
    assert len(messages) == 1  # MERGE 命中相同 message_id，未翻倍
    assert messages[0].text == "问（重试）"  # SET 更新了内容


def test_citations_roundtrip(ensured_schema):
    """agent 消息的 citations 序列化写入 + 读出还原往返。"""
    driver = ensured_schema
    conv = _create_test_conversation(driver)
    citations = [
        Citation(index=1, chunk_id="c1", document_id="d1", location="第1页", snippet="证据1"),
        Citation(index=2, chunk_id="c2", document_id="d1", location="第2页", snippet="证据2"),
    ]
    add_message(
        driver, conv.conversation_id, role="agent", text="答案[1][2]",
        embedding=_vec(), citations=citations, confidence="high",
    )
    messages = get_messages(driver, conv.conversation_id)
    assert len(messages) == 1
    m = messages[0]
    assert m.confidence == "high"
    assert len(m.citations) == 2
    assert m.citations[0].chunk_id == "c1"
    assert m.citations[1].index == 2


def test_user_message_no_citations(ensured_schema):
    driver = ensured_schema
    conv = _create_test_conversation(driver)
    m = add_message(driver, conv.conversation_id, role="user", text="问", embedding=_vec())
    assert m.confidence is None
    assert m.citations == []


def test_get_messages_ordered_by_turn(ensured_schema):
    driver = ensured_schema
    conv = _create_test_conversation(driver)
    for i in range(4):
        add_message(driver, conv.conversation_id, role="user", text=f"问{i}", embedding=_vec())
    messages = get_messages(driver, conv.conversation_id)
    assert [m.turn_index for m in messages] == [1, 2, 3, 4]


def test_get_messages_limit_window(ensured_schema):
    """limit 实现注入窗口：只取最近 N 条。"""
    driver = ensured_schema
    conv = _create_test_conversation(driver)
    for i in range(5):
        add_message(driver, conv.conversation_id, role="user", text=f"问{i}", embedding=_vec())
    recent = get_messages(driver, conv.conversation_id, limit=2)
    assert len(recent) == 2
    assert recent[0].turn_index == 4  # 取最后 2 条
    assert recent[1].turn_index == 5


def test_list_conversations_descending(ensured_schema):
    driver = ensured_schema
    c1 = _create_test_conversation(driver, title="早")
    c2 = _create_test_conversation(driver, title="晚")
    convs = list_conversations(driver)
    test_convs = [c for c in convs if c.conversation_id.startswith("conv_test_")]
    # 至少有这俩，按 created_at 降序
    assert len(test_convs) >= 2
    assert test_convs[0].created_at >= test_convs[1].created_at


def test_rename_conversation(ensured_schema):
    driver = ensured_schema
    conv = _create_test_conversation(driver, title="旧标题")
    renamed = rename_conversation(driver, conv.conversation_id, "新标题")
    assert renamed is not None
    assert renamed.title == "新标题"
    assert renamed.conversation_id == conv.conversation_id
    # 落库生效
    assert get_conversation(driver, conv.conversation_id).title == "新标题"


def test_rename_nonexistent_returns_none(ensured_schema):
    assert rename_conversation(ensured_schema, "conv_test_不存在", "标题") is None


def test_delete_conversation(ensured_schema):
    driver = ensured_schema
    conv = _create_test_conversation(driver)
    add_message(driver, conv.conversation_id, role="user", text="问", embedding=_vec())
    assert delete_conversation(driver, conv.conversation_id) is True
    assert get_conversation(driver, conv.conversation_id) is None
    assert get_messages(driver, conv.conversation_id) == []


def test_delete_nonexistent_returns_false(ensured_schema):
    assert delete_conversation(ensured_schema, "conv_test_不存在") is False
