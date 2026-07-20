"""将依赖会话上下文的追问改写为可独立检索的问题。"""

import logging

from app.clients import llm

logger = logging.getLogger(__name__)

_MAX_RETRIEVAL_QUESTION_LENGTH = 1000
_REWRITE_SYSTEM_PROMPT = (
    "你负责把同一会话中的追问改写成一个可独立理解的检索问题。\n"
    "只消解指代（如‘它’‘那个方案’‘前一个’），保留用户原始意图；不得回答问题，"
    "不得新增、猜测或补充对话中没有的事实。\n"
    "只输出改写后的一个问题，不要解释，不要加标题，最长 1000 个字符。"
)


def resolve_retrieval_question(
    original_question: str, history: list[dict] | None
) -> str:
    """生成一次独立检索问题；失败或空输出时安全回退原问题。"""
    if not history:
        return original_question

    messages: list[dict] = [{"role": "system", "content": _REWRITE_SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append(
        {
            "role": "user",
            "content": f"请只改写下面的当前追问：\n{original_question}",
        }
    )
    try:
        rewritten = llm.chat(messages)
    except Exception as exc:  # noqa: BLE001 - 重写失败不能让主问答失败
        logger.warning("追问改写失败，回退原问题: %s", exc)
        return original_question

    if not isinstance(rewritten, str):
        logger.warning("追问改写返回非文本，回退原问题")
        return original_question
    rewritten = rewritten.strip()[:_MAX_RETRIEVAL_QUESTION_LENGTH]
    return rewritten or original_question
