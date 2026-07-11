"""抽取数据模型：LLM 原始输出 / 编排产物 / 合并后写图形态 / 统计。

内部 snake_case；前端映射（下一板块序列化层做）：
entity_id->GraphNode.id, name->label, type->entityType, RELATES.type->relationType。
"""

from enum import Enum
from typing import Any, ClassVar

from pydantic import AliasChoices, BaseModel, Field, model_validator


class CandidateStatus(str, Enum):
    """Decision made by the candidate validation gate."""

    ACCEPTED = "accepted"
    REVIEW = "review"
    REJECTED = "rejected"


# Keep descriptive aliases for callers that use ``decision``/``validation``
# terminology.  The wire values remain the explicit contract above.
DecisionStatus = CandidateStatus
ValidationStatus = CandidateStatus
CandidateDecision = CandidateStatus
ValidationDecision = CandidateStatus


class Evidence(BaseModel):
    """Traceability information for one extraction candidate.

    An evidence reference must point to a source chunk and contain either a
    bounded text snippet or a valid half-open character range.  We reject
    malformed references instead of inventing provenance during validation.
    """

    MAX_TEXT_LENGTH: ClassVar[int] = 500

    chunk_id: str
    text: str | None = Field(
        default=None,
        max_length=MAX_TEXT_LENGTH,
        validation_alias=AliasChoices("text", "evidence_text", "snippet"),
    )
    char_start: int | None = Field(
        default=None,
        ge=0,
        validation_alias=AliasChoices("char_start", "source_start"),
    )
    char_end: int | None = Field(
        default=None,
        ge=0,
        validation_alias=AliasChoices("char_end", "source_end"),
    )

    @model_validator(mode="after")
    def _require_reference(self) -> "Evidence":
        if not self.chunk_id.strip():
            raise ValueError("chunk_id must not be empty")
        has_text = bool(self.text and self.text.strip())
        has_offsets = (
            self.char_start is not None
            and self.char_end is not None
            and self.char_end > self.char_start
        )
        if not has_text and not has_offsets:
            raise ValueError("evidence requires non-empty text or valid offsets")
        return self

    @property
    def source_start(self) -> int | None:
        return self.char_start

    @property
    def source_end(self) -> int | None:
        return self.char_end


EvidenceRef = Evidence


# ── LLM 原始返回（宽松，容忍噪声）──
class ExtractedEntity(BaseModel):
    name: str
    type: str
    description: str = ""
    evidence: Evidence | None = None


class ExtractedRelation(BaseModel):
    source: str  # 实体名，须 ∈ 本 chunk entities.name
    target: str
    type: str
    confidence: float = 0.5
    evidence: Evidence | None = None


class EntityCandidate(ExtractedEntity):
    """Explicit candidate form used by the validation layer."""

    confidence: float = 0.5


class RelationCandidate(ExtractedRelation):
    """Explicit relation candidate form used by the validation layer."""


ExtractedEntityCandidate = EntityCandidate
ExtractedRelationCandidate = RelationCandidate


class CandidateValidation(BaseModel):
    status: CandidateStatus
    diagnostics: list[str] = Field(default_factory=list)
    candidate: Any | None = None


ValidationResult = CandidateValidation


class ChunkExtractionResult(BaseModel):
    """json_object 校验目标：某 chunk 抽出的实体与关系。"""

    entities: list[ExtractedEntity] = Field(default_factory=list)
    relations: list[ExtractedRelation] = Field(default_factory=list)


# ── 编排层产物（带来源）──
class ChunkExtraction(BaseModel):
    chunk_id: str
    result: ChunkExtractionResult


class ExtractionFailure(BaseModel):
    chunk_id: str
    reason: str


# ── 合并后（写图前规范形态）──
class MergedEntity(BaseModel):
    entity_id: str  # f"{document_id}::{normalized_name}::{type}"
    name: str  # 首见原始名 -> 前端 label
    type: str  # -> 前端 entityType
    normalized_name: str  # name.lower().strip()
    description: str = ""
    mention_chunk_ids: list[str] = Field(default_factory=list)  # -> MENTIONS 边


class MergedRelation(BaseModel):
    source_id: str
    target_id: str
    type: str  # -> 前端 relationType
    confidence: float
    evidence_chunk_id: str


class DocumentExtraction(BaseModel):
    entities: list[MergedEntity] = Field(default_factory=list)
    relations: list[MergedRelation] = Field(default_factory=list)


class ExtractionStats(BaseModel):
    """一次文档抽取入库的结果统计。"""

    document_id: str
    entity_count: int
    relation_count: int
    mention_count: int
    failed_chunks: list[ExtractionFailure] = Field(default_factory=list)
    diagnostics: list[str] = Field(default_factory=list)
