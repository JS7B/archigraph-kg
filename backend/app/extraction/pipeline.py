"""对外编排：抽取 -> 合并 -> 写图。

前置：doc 的 Document/Chunk 已由 graph.ingest_document 写入（MENTIONS 用 MATCH 依赖 Chunk 存在）。
典型时序：ensure_schema -> embed_chunks -> ingest_document -> extract_and_ingest。
"""

from neo4j import Driver

from app.extraction.extractor import extract_document
from app.extraction.merge import merge_extractions
from app.extraction.models import ExtractionStats
from app.extraction.writer import write_extraction
from app.parsing.models import ParsedDocument


def extract_and_ingest(
    driver: Driver,
    doc: ParsedDocument,
    *,
    max_attempts: int = 3,
    database: str = "neo4j",
) -> ExtractionStats:
    """对已入库文档执行 抽取->合并->写图；单 chunk 失败记录跳过不中断。"""
    extractions, failures = extract_document(doc, max_attempts=max_attempts)
    merged = merge_extractions(doc.document_id, extractions)
    n_ent, n_rel, n_men = write_extraction(
        driver, doc.document_id, merged, database=database
    )
    return ExtractionStats(
        document_id=doc.document_id,
        entity_count=n_ent,
        relation_count=n_rel,
        mention_count=n_men,
        failed_chunks=failures,
    )
