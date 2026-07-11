"""逐 chunk 抽取编排：单 chunk 失败记录并跳过，不中断整文档。

容错风格沿用 parsing.repo_importer.parse_directory（try/except -> logger.error 跳过）。
"""

import logging
from collections.abc import Callable

from app.extraction.errors import ExtractionError
from app.extraction.llm_extract import extract_chunk
from app.extraction.models import ChunkExtraction, ExtractionFailure
from app.parsing.models import ExtractionPolicy, ParsedDocument

logger = logging.getLogger(__name__)


def extract_document(
    doc: ParsedDocument,
    *,
    max_attempts: int = 3,
    on_progress: Callable[[int, int], None] | None = None,
) -> tuple[list[ChunkExtraction], list[ExtractionFailure]]:
    """逐 chunk 抽取，返回 (成功抽取列表, 失败列表)。

    on_progress(index, total)：每个 chunk 开始抽取前回调（index 从 1 起），
    供上层发进度事件——抽取是长任务（每 chunk 一次 LLM 调用），没有细粒度
    进度时前端会呈现"卡死"错觉。
    """
    extractions: list[ChunkExtraction] = []
    failures: list[ExtractionFailure] = []
    total = len(doc.chunks)
    for index, chunk in enumerate(doc.chunks, start=1):
        if on_progress is not None:
            on_progress(index, total)
        chunk_id = f"{doc.document_id}#{chunk.chunk_index}"
        if chunk.extraction_policy is ExtractionPolicy.SKIP:
            continue
        try:
            kwargs = {"max_attempts": max_attempts}
            if chunk.extraction_policy is not ExtractionPolicy.NORMAL:
                kwargs["extraction_policy"] = chunk.extraction_policy
            if chunk.language is not None:
                kwargs["language"] = chunk.language
            result = extract_chunk(chunk_id, chunk.text, **kwargs)
            extractions.append(ChunkExtraction(chunk_id=chunk_id, result=result))
        except ExtractionError as exc:
            logger.error("跳过抽取失败的 chunk %s: %s", chunk_id, exc)
            failures.append(ExtractionFailure(chunk_id=chunk_id, reason=exc.reason))
    return extractions, failures
