"""问答 prompt：含引用要求、含上下文与问题。"""

from app.qa.prompt import ANSWER_SYSTEM_PROMPT, build_answer_messages


def test_system_prompt_requires_citation():
    assert "[1]" in ANSWER_SYSTEM_PROMPT or "角标" in ANSWER_SYSTEM_PROMPT
    assert "无法回答" in ANSWER_SYSTEM_PROMPT  # 压幻觉指令


def test_messages_carry_context_and_question():
    msgs = build_answer_messages("什么是知识图谱？", "[1] 知识图谱是…")
    assert len(msgs) == 2
    assert msgs[0]["role"] == "system"
    assert "什么是知识图谱？" in msgs[1]["content"]
    assert "[1] 知识图谱是…" in msgs[1]["content"]
