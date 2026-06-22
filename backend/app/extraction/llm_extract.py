"""单 chunk 抽取：调 LLM（JSON 模式）+ 解析校验 + 手写轻量重试。"""

import json
import logging
import time

from openai import OpenAIError
from pydantic import ValidationError

from app.clients import llm
from app.extraction.errors import ExtractionError
from app.extraction.models import ChunkExtractionResult
from app.extraction.prompt import build_messages

logger = logging.getLogger(__name__)

_JSON_FORMAT = {"type": "json_object"}


def extract_chunk(
    chunk_id: str,
    chunk_text: str,
    *,
    max_attempts: int = 3,
    base_delay: float = 1.0,
) -> ChunkExtractionResult:
    """抽取单个 chunk 的实体与关系；失败按指数退避重试，耗尽抛 ExtractionError。"""
    messages = build_messages(chunk_text)
    last_reason = ""
    for attempt in range(1, max_attempts + 1):
        try:
            raw = llm.chat(messages, response_format=_JSON_FORMAT)
            return ChunkExtractionResult.model_validate(json.loads(raw))
        except (json.JSONDecodeError, ValidationError, OpenAIError, ValueError) as exc:
            last_reason = f"{type(exc).__name__}: {exc}"
            logger.warning("chunk %s 抽取第 %d 次失败：%s", chunk_id, attempt, last_reason)
            if attempt < max_attempts:
                time.sleep(base_delay * 2 ** (attempt - 1))
    raise ExtractionError(chunk_id=chunk_id, reason=last_reason)
