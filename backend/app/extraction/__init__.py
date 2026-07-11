"""实体识别与关系抽取层：LLM 抽取、文档内合并去重、写图（MENTIONS/RELATES）。"""

from app.extraction.errors import ExtractionError
from app.extraction.extractor import extract_document
from app.extraction.llm_extract import extract_chunk
from app.extraction.merge import merge_extractions
from app.extraction.models import (
    CandidateDecision,
    CandidateStatus,
    CandidateValidation,
    DecisionStatus,
    ChunkExtraction,
    ChunkExtractionResult,
    DocumentExtraction,
    EntityCandidate,
    Evidence,
    EvidenceRef,
    ExtractedEntity,
    ExtractedRelation,
    ExtractedEntityCandidate,
    ExtractedRelationCandidate,
    ExtractionFailure,
    ExtractionStats,
    MergedEntity,
    MergedRelation,
    RelationCandidate,
    ValidationStatus,
    ValidationDecision,
    ValidationResult,
)
from app.extraction.pipeline import extract_and_ingest
from app.extraction.validation import (
    validate_chunk_result,
    validate_entity_candidate,
    validate_extraction_candidates,
    validate_relation_candidate,
)
from app.extraction.writer import write_extraction

__all__ = [
    "extract_and_ingest",
    "extract_document",
    "extract_chunk",
    "merge_extractions",
    "write_extraction",
    "ExtractionError",
    "ExtractionStats",
    "CandidateStatus",
    "CandidateDecision",
    "DecisionStatus",
    "ValidationDecision",
    "ValidationStatus",
    "Evidence",
    "EvidenceRef",
    "EntityCandidate",
    "RelationCandidate",
    "ExtractedEntityCandidate",
    "ExtractedRelationCandidate",
    "CandidateValidation",
    "ValidationResult",
    "validate_entity_candidate",
    "validate_relation_candidate",
    "validate_chunk_result",
    "validate_extraction_candidates",
    "ChunkExtraction",
    "ChunkExtractionResult",
    "DocumentExtraction",
    "ExtractedEntity",
    "ExtractedRelation",
    "ExtractionFailure",
    "MergedEntity",
    "MergedRelation",
]
