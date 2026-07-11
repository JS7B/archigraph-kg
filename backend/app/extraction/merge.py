"""文档内实体合并去重 + 关系两端从实体名解析到 entity_id。

合并键 normalized_name（= name.lower().strip()），不含 type——同名异型（如 React 被
一处标「技术」、另一处标「概念」）归并为同一节点，避免碎成两点。type 取该名下出现
次数最多者（并列取先见）。entity_id = f"{document_id}::{normalized_name}"。
跨文档不合并（entity_id 含 document_id）。
"""

import logging
from collections import Counter

from app.extraction.models import (
    ChunkExtraction,
    DocumentExtraction,
    ExtractedEntity,
    MergedEntity,
    MergedRelation,
)
from app.extraction.validation import (
    validate_entity_candidate,
    validate_relation_candidate,
)

logger = logging.getLogger(__name__)

_MAX_DESC = 500  # 聚合描述限长，避免无限增长
ALLOWED_RELATION_TYPES = frozenset(
    {"依赖", "组成", "使用", "导致", "缓解", "属于", "对比", "影响", "约束"}
)
MIN_RELATION_CONFIDENCE = 0.5


def _normalize(name: str) -> str:
    return name.casefold().strip()


def merge_extractions(
    document_id: str,
    extractions: list[ChunkExtraction],
    *,
    diagnostics: list[str] | None = None,
) -> DocumentExtraction:
    """把逐 chunk 抽取结果合并为文档级实体与关系。"""
    entities: dict[str, MergedEntity] = {}
    accepted_entities: list[ExtractedEntity] = []
    # 归一名 -> 各 type 的出现计数，用于 type 多数决（并列取先见，靠 Counter 插入序）
    type_counts: dict[str, Counter] = {}

    def _entity_id(norm: str) -> str:
        return f"{document_id}::{norm}"

    def _report(chunk_id: str, kind: str, messages: list[str]) -> None:
        message = f"{chunk_id} {kind}: {'; '.join(messages)}"
        logger.warning("rejected extraction candidate: %s", message)
        if diagnostics is not None:
            diagnostics.append(message)

    # 第一遍：按 normalized_name 合并实体，累计 type 计数
    for extraction in extractions:
        chunk_id = extraction.chunk_id
        for ent in extraction.result.entities:
            validation = validate_entity_candidate(ent)
            if validation.status.value != "accepted":
                _report(chunk_id, "entity", validation.diagnostics)
                continue
            accepted_entities.append(ent)
            norm = _normalize(ent.name)
            type_counts.setdefault(norm, Counter())[ent.type] += 1
            if norm not in entities:
                entities[norm] = MergedEntity(
                    entity_id=_entity_id(norm),
                    name=ent.name,
                    type=ent.type,  # 临时值，第一遍后按多数决改写
                    normalized_name=norm,
                    description=ent.description,
                    mention_chunk_ids=[chunk_id],
                )
            else:
                merged = entities[norm]
                if chunk_id not in merged.mention_chunk_ids:
                    merged.mention_chunk_ids.append(chunk_id)
                if ent.description and ent.description not in merged.description:
                    combined = (
                        f"{merged.description} | {ent.description}"
                        if merged.description
                        else ent.description
                    )
                    merged.description = combined[:_MAX_DESC]

    # type 多数决：Counter.most_common 按计数降序、并列保持插入序（= 先见者优先）
    for norm, merged in entities.items():
        merged.type = type_counts[norm].most_common(1)[0][0]

    # 第二遍：解析关系两端到 entity_id，去重
    relations: dict[tuple[str, str, str], MergedRelation] = {}
    for extraction in extractions:
        chunk_id = extraction.chunk_id
        for rel in extraction.result.relations:
            validation = validate_relation_candidate(rel, accepted_entities)
            if validation.status.value != "accepted":
                _report(chunk_id, "relation", validation.diagnostics)
                continue
            relation_type = rel.type.strip()
            relation_diagnostics: list[str] = []
            if relation_type not in ALLOWED_RELATION_TYPES:
                relation_diagnostics.append(
                    f"type: unknown relation type {rel.type!r}"
                )
            if rel.confidence < MIN_RELATION_CONFIDENCE:
                relation_diagnostics.append(
                    f"confidence: below minimum {MIN_RELATION_CONFIDENCE:g}"
                )
            if relation_diagnostics:
                _report(chunk_id, "relation", relation_diagnostics)
                continue
            source_id = _resolve(rel.source, entities, _entity_id)
            target_id = _resolve(rel.target, entities, _entity_id)
            if source_id is None or target_id is None:
                _report(
                    chunk_id,
                    "relation",
                    ["endpoint: source or target is not an accepted entity"],
                )
                continue
            rkey = (source_id, target_id, relation_type)
            existing = relations.get(rkey)
            if existing is None or rel.confidence > existing.confidence:
                relations[rkey] = MergedRelation(
                    source_id=source_id,
                    target_id=target_id,
                    type=relation_type,
                    confidence=rel.confidence,
                    evidence_chunk_id=rel.evidence.chunk_id,
                )

    return DocumentExtraction(
        entities=list(entities.values()), relations=list(relations.values())
    )


def _resolve(name, entities, entity_id_fn) -> str | None:
    """把关系端点实体名解析为 entity_id；归一名未抽到实体则返回 None。"""
    norm = _normalize(name)
    if norm not in entities:
        return None
    return entity_id_fn(norm)
