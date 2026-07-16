"""逐 chunk 抽取编排：有限并发，单 chunk 失败不影响整文档。

容错风格沿用 parsing.repo_importer.parse_directory（try/except -> logger.error 跳过）。
"""

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.extraction.errors import ExtractionError
from app.extraction.llm_extract import extract_chunk
from app.extraction.models import ChunkExtraction, ExtractionFailure
from app.parsing.models import Chunk, ExtractionPolicy, ParsedDocument

logger = logging.getLogger(__name__)


def extract_document(
    doc: ParsedDocument,
    *,
    max_attempts: int = 3,
    max_workers: int = 3,
    on_progress: Callable[[int, int], None] | None = None,
) -> tuple[list[ChunkExtraction], list[ExtractionFailure]]:
    """有限并发抽取非 SKIP chunk，返回按文档原始顺序排列的结果。

    on_progress(completed, total)：每个可抽取 chunk 完成后回调；SKIP chunk
    不提交、不计入 total。仅 ExtractionError 被隔离，其他异常仍使整文档失败。
    """
    if max_workers < 1:
        raise ValueError("max_workers must be at least 1")

    extractable = [
        (position, chunk)
        for position, chunk in enumerate(doc.chunks)
        if chunk.extraction_policy is not ExtractionPolicy.SKIP
    ]
    total = len(extractable)
    if total == 0:
        return [], []

    successful_by_position: dict[int, ChunkExtraction] = {}
    failed_by_position: dict[int, ExtractionFailure] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_positions = {
            executor.submit(_extract_one, doc.document_id, chunk, max_attempts): position
            for position, chunk in extractable
        }
        completed = 0
        for future in as_completed(future_positions):
            position = future_positions[future]
            chunk = doc.chunks[position]
            chunk_id = f"{doc.document_id}#{chunk.chunk_index}"
            completed += 1
            try:
                successful_by_position[position] = future.result()
            except ExtractionError as exc:
                logger.error("跳过抽取失败的 chunk %s: %s", chunk_id, exc)
                failed_by_position[position] = ExtractionFailure(
                    chunk_id=chunk_id, reason=exc.reason
                )
            finally:
                if on_progress is not None:
                    on_progress(completed, total)

    # merge_extractions 对“首见”有明确语义；必须按文档位置恢复，不能按
    # future 完成顺序或 chunk_id 字符串排序。
    extractions = [
        successful_by_position[position]
        for position, _ in extractable
        if position in successful_by_position
    ]
    failures = [
        failed_by_position[position]
        for position, _ in extractable
        if position in failed_by_position
    ]
    return extractions, failures


def _extract_one(
    document_id: str, chunk: Chunk, max_attempts: int
) -> ChunkExtraction:
    """在线程池中抽取一个 chunk；异常原样交回主编排线程处理。"""
    chunk_id = f"{document_id}#{chunk.chunk_index}"
    kwargs = {"max_attempts": max_attempts}
    if chunk.extraction_policy is not ExtractionPolicy.NORMAL:
        kwargs["extraction_policy"] = chunk.extraction_policy
    if chunk.language is not None:
        kwargs["language"] = chunk.language
    result = extract_chunk(chunk_id, chunk.text, **kwargs)
    return ChunkExtraction(chunk_id=chunk_id, result=result)
