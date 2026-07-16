"""对外编排：抽取 -> 合并 -> 写图。

前置：doc 的 Document/Chunk 已由 graph.ingest_document 写入（MENTIONS 用 MATCH 依赖 Chunk 存在）。
典型时序：ensure_schema -> embed_chunks -> ingest_document -> extract_and_ingest。
"""

from collections.abc import Callable

from neo4j import Driver

from app.extraction.extractor import extract_document
from app.extraction.merge import merge_extractions
from app.extraction.models import ExtractionStats
from app.extraction.writer import write_extraction
from app.parsing.models import ParsedDocument
from app.resolution.models import SourceEntityRecord
from app.resolution.service import resolve_source_entities


def extract_and_ingest(
    driver: Driver,
    doc: ParsedDocument,
    *,
    max_attempts: int = 3,
    max_workers: int = 3,
    database: str = "neo4j",
    on_progress: Callable[[int, int], None] | None = None,
) -> ExtractionStats:
    """对已入库文档执行 抽取->合并->写图；单 chunk 失败记录跳过不中断。

    on_progress 透传给 extract_document（每个可抽取 chunk 完成后回调）。
    """
    extractions, failures = extract_document(
        doc,
        max_attempts=max_attempts,
        max_workers=max_workers,
        on_progress=on_progress,
    )
    diagnostics: list[str] = []
    merged = merge_extractions(doc.document_id, extractions, diagnostics=diagnostics)
    n_ent, n_rel, n_men = write_extraction(
        driver, doc.document_id, merged, database=database
    )
    resolution = resolve_source_entities(
        driver,
        [
            SourceEntityRecord(
                entity_id=entity.entity_id,
                name=entity.name,
                entity_type=entity.type,
                normalized_name=entity.normalized_name,
                document_id=doc.document_id,
                mention_chunk_ids=entity.mention_chunk_ids,
            )
            for entity in merged.entities
        ],
        database=database,
    )
    diagnostics.extend(resolution.diagnostics)
    return ExtractionStats(
        document_id=doc.document_id,
        entity_count=n_ent,
        relation_count=n_rel,
        mention_count=n_men,
        failed_chunks=failures,
        diagnostics=diagnostics,
    )
