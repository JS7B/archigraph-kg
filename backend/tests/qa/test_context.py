"""context 组装：chunk 编号与 Citation 对齐、location 可读、路径文本拼装。"""

from app.graph.search import ChunkHit
from app.qa.context import build_context
from app.qa.models import RelationPath


def _hit(i: int, *, page=None, headings=None) -> ChunkHit:
    return ChunkHit(
        chunk_id=f"d#{i}",
        document_id="d",
        chunk_index=i,
        text=f"片段{i}内容",
        char_start=i * 10,
        char_end=i * 10 + 5,
        page=page,
        heading_path=headings or [],
        score=1.0 - i * 0.1,
    )


def test_citation_index_aligns_with_numbering():
    ctx, citations = build_context([_hit(0), _hit(1)], [])
    assert "[1] 片段0内容" in ctx
    assert "[2] 片段1内容" in ctx
    assert citations[0].index == 1 and citations[0].chunk_id == "d#0"
    assert citations[1].index == 2 and citations[1].chunk_id == "d#1"


def test_location_includes_page_and_heading():
    _, citations = build_context([_hit(0, page=3, headings=["一章", "一节"])], [])
    loc = citations[0].location
    assert "第3页" in loc
    assert "一章 > 一节" in loc
    assert "字符 0-5" in loc


def test_relation_paths_rendered():
    paths = [RelationPath(source_name="A", target_name="B", type="依赖", evidence_chunk_id="d#0")]
    ctx, _ = build_context([_hit(0)], paths)
    assert "【相关实体关系】" in ctx
    assert "A -[依赖]-> B" in ctx


def test_no_paths_no_relation_section():
    ctx, _ = build_context([_hit(0)], [])
    assert "【相关实体关系】" not in ctx
