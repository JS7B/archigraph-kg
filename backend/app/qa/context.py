"""上下文组装：把召回 chunk 编号成带角标的上下文，并同步产出 Citation 列表。

chunk 编号 [1][2]… 与 Citation.index 一一对应，是「引用可追溯」的锚点：
LLM 用 [n] 引用，前端再用 Citation.chunk_id 反查原文。实体关系路径单列一段供 LLM 参考。
"""

from app.graph.search import ChunkHit
from app.qa.models import Citation, RelationPath

_SNIPPET_LEN = 120


def _location(hit: ChunkHit) -> str:
    """把 page / heading_path / 字符区间拼成可读位置串。"""
    parts: list[str] = []
    if hit.page is not None:
        parts.append(f"第{hit.page}页")
    if hit.heading_path:
        parts.append(" > ".join(hit.heading_path))
    parts.append(f"字符 {hit.char_start}-{hit.char_end}")
    return " · ".join(parts)


def build_context(
    chunks: list[ChunkHit], paths: list[RelationPath]
) -> tuple[str, list[Citation]]:
    """组装上下文文本与 Citation 列表。返回 (context_str, citations)。"""
    citations: list[Citation] = []
    lines: list[str] = ["【文档片段】"]
    for i, hit in enumerate(chunks, start=1):
        lines.append(f"[{i}] {hit.text}")
        citations.append(
            Citation(
                index=i,
                chunk_id=hit.chunk_id,
                document_id=hit.document_id,
                location=_location(hit),
                snippet=hit.text[:_SNIPPET_LEN],
            )
        )

    if paths:
        lines.append("\n【相关实体关系】")
        for p in paths:
            lines.append(f"{p.source_name} -[{p.type}]-> {p.target_name}")

    return "\n".join(lines), citations
