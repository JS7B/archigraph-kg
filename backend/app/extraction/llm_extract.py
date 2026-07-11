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
from app.parsing.models import ExtractionPolicy

logger = logging.getLogger(__name__)

_JSON_FORMAT = {"type": "json_object"}


def _parse_result(raw: str) -> ChunkExtractionResult:
    """Parse the model response without letting model defaults hide omissions."""
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise TypeError("extraction output must be a JSON object")
    for field_name in ("entities", "relations"):
        if field_name not in payload:
            raise ValueError(f"missing required field: {field_name}")
        if not isinstance(payload[field_name], list):
            raise TypeError(f"{field_name} must be a JSON array")
    return ChunkExtractionResult.model_validate(payload)


def extract_chunk(
    chunk_id: str,
    chunk_text: str,
    *,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    extraction_policy: ExtractionPolicy | str = ExtractionPolicy.NORMAL,
    language: str | None = None,
) -> ChunkExtractionResult:
    """抽取单个 chunk 的实体与关系；失败按指数退避重试，耗尽抛 ExtractionError。"""
    messages = build_messages(
        chunk_text,
        extraction_policy=extraction_policy,
        language=language,
        chunk_id=chunk_id,
    )
    last_reason = ""
    for attempt in range(1, max_attempts + 1):
        try:
            raw = llm.chat(messages, response_format=_JSON_FORMAT)
            return _parse_result(raw)
        except (
            json.JSONDecodeError,
            ValidationError,
            OpenAIError,
            TypeError,
            ValueError,
        ) as exc:
            last_reason = f"{type(exc).__name__}: {exc}"
            logger.warning("chunk %s 抽取第 %d 次失败：%s", chunk_id, attempt, last_reason)
            if attempt < max_attempts:
                time.sleep(base_delay * 2 ** (attempt - 1))
    raise ExtractionError(chunk_id=chunk_id, reason=last_reason)
