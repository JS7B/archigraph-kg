"""文档内实体合并去重 + 关系两端从实体名解析到 entity_id。

合并键 (normalized_name, type)，normalized_name = name.lower().strip()。
entity_id = f"{document_id}::{normalized_name}::{type}"（:: 避开 chunk_id 的 #）。
跨文档不合并（entity_id 含 document_id）。
"""

import logging

from app.extraction.models import (
    ChunkExtraction,
    DocumentExtraction,
    MergedEntity,
    MergedRelation,
)

logger = logging.getLogger(__name__)

_MAX_DESC = 500  # 聚合描述限长，避免无限增长


def _normalize(name: str) -> str:
    return name.lower().strip()


def merge_extractions(
    document_id: str, extractions: list[ChunkExtraction]
) -> DocumentExtraction:
    """把逐 chunk 抽取结果合并为文档级实体与关系。"""
    entities: dict[tuple[str, str], MergedEntity] = {}
    # 归一名 -> 该名下出现过的 type 集合，用于关系两端解析
    name_to_types: dict[str, list[str]] = {}

    def _entity_id(norm: str, type_: str) -> str:
        return f"{document_id}::{norm}::{type_}"

    # 第一遍：合并实体
    for extraction in extractions:
        chunk_id = extraction.chunk_id
        for ent in extraction.result.entities:
            norm = _normalize(ent.name)
            if not norm:
                continue
            key = (norm, ent.type)
            if key not in entities:
                entities[key] = MergedEntity(
                    entity_id=_entity_id(norm, ent.type),
                    name=ent.name,
                    type=ent.type,
                    normalized_name=norm,
                    description=ent.description,
                    mention_chunk_ids=[chunk_id],
                )
                name_to_types.setdefault(norm, [])
                if ent.type not in name_to_types[norm]:
                    name_to_types[norm].append(ent.type)
            else:
                merged = entities[key]
                if chunk_id not in merged.mention_chunk_ids:
                    merged.mention_chunk_ids.append(chunk_id)
                if ent.description and ent.description not in merged.description:
                    combined = (
                        f"{merged.description} | {ent.description}"
                        if merged.description
                        else ent.description
                    )
                    merged.description = combined[:_MAX_DESC]

    # 第二遍：解析关系两端到 entity_id，去重
    relations: dict[tuple[str, str, str], MergedRelation] = {}
    for extraction in extractions:
        chunk_id = extraction.chunk_id
        for rel in extraction.result.relations:
            source_id = _resolve(rel.source, name_to_types, _entity_id)
            target_id = _resolve(rel.target, name_to_types, _entity_id)
            if source_id is None or target_id is None:
                logger.warning(
                    "丢弃无法解析两端的关系 %s -[%s]-> %s（chunk %s）",
                    rel.source, rel.type, rel.target, chunk_id,
                )
                continue
            rkey = (source_id, target_id, rel.type)
            existing = relations.get(rkey)
            if existing is None or rel.confidence > existing.confidence:
                relations[rkey] = MergedRelation(
                    source_id=source_id,
                    target_id=target_id,
                    type=rel.type,
                    confidence=rel.confidence,
                    evidence_chunk_id=chunk_id,
                )

    return DocumentExtraction(
        entities=list(entities.values()), relations=list(relations.values())
    )


def _resolve(name, name_to_types, entity_id_fn) -> str | None:
    """把关系端点实体名解析为 entity_id；归一名未抽到实体则返回 None。"""
    norm = _normalize(name)
    types = name_to_types.get(norm)
    if not types:
        return None
    if len(types) > 1:
        logger.warning("实体名 %r 对应多个类型 %s，取首个", name, types)
    return entity_id_fn(norm, types[0])
