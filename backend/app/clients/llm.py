"""OpenAI-compatible LLM 薄封装：chat / embedding，以及配置状态探测。"""

from openai import OpenAI

from app.config import get_settings

# 占位值标记：.env.example 里的 sk-your-key-here / https://your-provider 这类未填真实值。
_PLACEHOLDER_MARKERS = ("your-", "please-change")


def _client() -> OpenAI:
    settings = get_settings()
    return OpenAI(base_url=settings.openai_base_url, api_key=settings.openai_api_key)


def is_configured() -> bool:
    """判断 LLM 是否已配置真实值（非空且不含占位标记）。"""
    settings = get_settings()
    base_url = settings.openai_base_url
    api_key = settings.openai_api_key
    if not base_url or not api_key:
        return False
    combined = f"{base_url} {api_key}".lower()
    return not any(marker in combined for marker in _PLACEHOLDER_MARKERS)


def chat(messages: list[dict], *, response_format: dict | None = None) -> str:
    """调用 chat completion，返回首条回复文本。

    response_format 透传给 OpenAI-compatible 端点（如 {"type": "json_object"} 开启 JSON 模式）；
    缺省 None 时行为与原先完全一致。
    """
    settings = get_settings()
    kwargs: dict = {"model": settings.chat_model, "messages": messages}
    if response_format is not None:
        kwargs["response_format"] = response_format
    resp = _client().chat.completions.create(**kwargs)
    return resp.choices[0].message.content


def embed(texts: list[str]) -> list[list[float]]:
    """对文本列表生成向量。"""
    settings = get_settings()
    resp = _client().embeddings.create(
        model=settings.embedding_model,
        input=texts,
    )
    return [item.embedding for item in resp.data]
