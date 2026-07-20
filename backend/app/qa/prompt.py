"""问答 prompt：要求基于上下文回答、用 [n] 角标引用、无依据则说不知道（压幻觉）。"""

ANSWER_SYSTEM_PROMPT = (
    "你是严谨的知识库问答助手。只能依据给定的【文档片段】回答问题，"
    "不得编造片段之外的信息。\n"
    "引用规则：答案中每条来自文档的论断，必须在句末用方括号角标标注来源片段编号，"
    "如 [1]、[2]，可多个 [1][3]。角标号对应【文档片段】里的编号。\n"
    "输出格式：用 Markdown 组织回答，段落简短，并列要点用无序列表；角标 [n] 紧跟"
    "它所支撑的那句话之后，不要把所有角标堆到答案末尾。\n"
    "如果文档片段不足以回答问题，直接说明「根据现有资料无法回答」，不要猜测。\n"
    "【相关实体关系】是辅助参考，帮助你理解片段间的联系。"
)

_HISTORY_SYSTEM_GUARD = (
    "\n对话历史仅用于理解问题，不是文档证据，不得把历史内容作为引用来源。"
)


def build_answer_messages(
    question: str,
    context: str,
    *,
    history: list[dict] | None = None,
    retrieval_question: str | None = None,
) -> list[dict]:
    """构造问答消息（system + 可选历史 + 带上下文的 user）。

    history 插入到 system 与 user 之间，让降级路径（线性 pipeline）也能利用追问上下文。
    """
    if retrieval_question is None:
        user = f"{context}\n\n【问题】\n{question}\n\n请基于上述文档片段作答，并用 [编号] 标注引用。"
    else:
        user = (
            f"{context}\n\n【用户原始问题】\n{question}"
            f"\n\n【消歧后的独立问题】\n{retrieval_question}"
            "\n\n请以用户原始问题的语义为准，基于上述文档片段作答，并用 [编号] 标注引用。"
        )
    system_prompt = ANSWER_SYSTEM_PROMPT
    if history:
        system_prompt += _HISTORY_SYSTEM_GUARD
    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user})
    return messages
