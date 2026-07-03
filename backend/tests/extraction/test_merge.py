"""合并去重：跨 chunk 同名合并、归一、关系两端解析、丢弃无解析关系、关系去重。"""

from app.extraction.merge import merge_extractions
from app.extraction.models import (
    ChunkExtraction,
    ChunkExtractionResult,
    ExtractedEntity,
    ExtractedRelation,
)


def _ce(chunk_id, entities=None, relations=None) -> ChunkExtraction:
    return ChunkExtraction(
        chunk_id=chunk_id,
        result=ChunkExtractionResult(
            entities=entities or [], relations=relations or []
        ),
    )


def test_same_name_type_merges_across_chunks():
    extractions = [
        _ce("d#0", entities=[ExtractedEntity(name="FastAPI", type="技术概念", description="A")]),
        _ce("d#1", entities=[ExtractedEntity(name="FastAPI", type="技术概念", description="B")]),
    ]
    result = merge_extractions("d", extractions)
    assert len(result.entities) == 1
    ent = result.entities[0]
    assert ent.mention_chunk_ids == ["d#0", "d#1"]
    assert "A" in ent.description and "B" in ent.description


def test_case_and_space_normalized():
    extractions = [
        _ce("d#0", entities=[ExtractedEntity(name="FastAPI", type="技术概念")]),
        _ce("d#1", entities=[ExtractedEntity(name="  fastapi ", type="技术概念")]),
    ]
    result = merge_extractions("d", extractions)
    assert len(result.entities) == 1
    assert result.entities[0].normalized_name == "fastapi"


def test_entity_id_format():
    # entity_id 只含 document_id::normalized_name（不再含 type）
    extractions = [_ce("d#0", entities=[ExtractedEntity(name="Neo4j", type="技术")])]
    result = merge_extractions("mydoc", extractions)
    assert result.entities[0].entity_id == "mydoc::neo4j"


def test_same_name_different_type_merges_with_majority_type():
    # React 被标 3 次「技术」、1 次「概念」→ 合并成 1 个实体，type 取多数「技术」
    extractions = [
        _ce("d#0", entities=[ExtractedEntity(name="React", type="技术")]),
        _ce("d#1", entities=[ExtractedEntity(name="React", type="概念")]),
        _ce("d#2", entities=[ExtractedEntity(name="React", type="技术")]),
        _ce("d#3", entities=[ExtractedEntity(name="React", type="技术")]),
    ]
    result = merge_extractions("d", extractions)
    assert len(result.entities) == 1
    ent = result.entities[0]
    assert ent.type == "技术"
    assert ent.entity_id == "d::react"
    assert ent.mention_chunk_ids == ["d#0", "d#1", "d#2", "d#3"]


def test_type_tie_keeps_first_seen():
    # 「技术」与「概念」各 1 次并列 → 取先见的「概念」
    extractions = [
        _ce("d#0", entities=[ExtractedEntity(name="Agent", type="概念")]),
        _ce("d#1", entities=[ExtractedEntity(name="Agent", type="技术")]),
    ]
    result = merge_extractions("d", extractions)
    assert result.entities[0].type == "概念"


def test_relation_endpoints_resolved():
    extractions = [
        _ce(
            "d#0",
            entities=[
                ExtractedEntity(name="FastAPI", type="技术"),
                ExtractedEntity(name="Pydantic", type="技术"),
            ],
            relations=[
                ExtractedRelation(source="FastAPI", target="Pydantic", type="依赖", confidence=0.8)
            ],
        )
    ]
    result = merge_extractions("d", extractions)
    assert len(result.relations) == 1
    rel = result.relations[0]
    assert rel.source_id == "d::fastapi"
    assert rel.target_id == "d::pydantic"
    assert rel.evidence_chunk_id == "d#0"


def test_unresolvable_relation_dropped():
    # target "Unknown" 没有对应实体，整条关系丢弃，不报错
    extractions = [
        _ce(
            "d#0",
            entities=[ExtractedEntity(name="FastAPI", type="技术概念")],
            relations=[
                ExtractedRelation(source="FastAPI", target="Unknown", type="依赖", confidence=0.7)
            ],
        )
    ]
    result = merge_extractions("d", extractions)
    assert result.relations == []


def test_relation_dedup_keeps_higher_confidence():
    rel_lo = ExtractedRelation(source="A", target="B", type="使用", confidence=0.3)
    rel_hi = ExtractedRelation(source="A", target="B", type="使用", confidence=0.9)
    ents = [ExtractedEntity(name="A", type="项目"), ExtractedEntity(name="B", type="项目")]
    extractions = [
        _ce("d#0", entities=ents, relations=[rel_lo]),
        _ce("d#1", entities=ents, relations=[rel_hi]),
    ]
    result = merge_extractions("d", extractions)
    assert len(result.relations) == 1
    assert result.relations[0].confidence == 0.9
