"""抽取数据模型：LLM 原始输出 / 编排产物 / 合并后写图形态 / 统计。

内部 snake_case；前端映射（下一板块序列化层做）：
entity_id->GraphNode.id, name->label, type->entityType, RELATES.type->relationType。
"""

from pydantic import BaseModel, Field


# ── LLM 原始返回（宽松，容忍噪声）──
class ExtractedEntity(BaseModel):
    name: str
    type: str
    description: str = ""


class ExtractedRelation(BaseModel):
    source: str  # 实体名，须 ∈ 本 chunk entities.name
    target: str
    type: str
    confidence: float = 0.5


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
