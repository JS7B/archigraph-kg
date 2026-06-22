"""实体识别与关系抽取层：LLM 抽取、文档内合并去重、写图（MENTIONS/RELATES）。"""

from app.extraction.errors import ExtractionError
from app.extraction.extractor import extract_document
from app.extraction.llm_extract import extract_chunk
from app.extraction.merge import merge_extractions
from app.extraction.models import (
    ChunkExtraction,
    ChunkExtractionResult,
    DocumentExtraction,
    ExtractedEntity,
    ExtractedRelation,
    ExtractionFailure,
    ExtractionStats,
    MergedEntity,
    MergedRelation,
)
from app.extraction.pipeline import extract_and_ingest
from app.extraction.writer import write_extraction

__all__ = [
    "extract_and_ingest",
    "extract_document",
    "extract_chunk",
    "merge_extractions",
    "write_extraction",
    "ExtractionError",
    "ExtractionStats",
    "ChunkExtraction",
    "ChunkExtractionResult",
    "DocumentExtraction",
    "ExtractedEntity",
    "ExtractedRelation",
    "ExtractionFailure",
    "MergedEntity",
    "MergedRelation",
]
