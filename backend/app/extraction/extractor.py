"""逐 chunk 抽取编排：单 chunk 失败记录并跳过，不中断整文档。

容错风格沿用 parsing.repo_importer.parse_directory（try/except -> logger.error 跳过）。
"""

import logging

from app.extraction.errors import ExtractionError
from app.extraction.llm_extract import extract_chunk
from app.extraction.models import ChunkExtraction, ExtractionFailure
from app.parsing.models import ParsedDocument

logger = logging.getLogger(__name__)


def extract_document(
    doc: ParsedDocument, *, max_attempts: int = 3
) -> tuple[list[ChunkExtraction], list[ExtractionFailure]]:
    """逐 chunk 抽取，返回 (成功抽取列表, 失败列表)。"""
    extractions: list[ChunkExtraction] = []
    failures: list[ExtractionFailure] = []
    for chunk in doc.chunks:
        chunk_id = f"{doc.document_id}#{chunk.chunk_index}"
        try:
            result = extract_chunk(chunk_id, chunk.text, max_attempts=max_attempts)
            extractions.append(ChunkExtraction(chunk_id=chunk_id, result=result))
        except ExtractionError as exc:
            logger.error("跳过抽取失败的 chunk %s: %s", chunk_id, exc)
            failures.append(ExtractionFailure(chunk_id=chunk_id, reason=exc.reason))
    return extractions, failures
