"""图谱写入：把 ParsedDocument 的 Document 与 Chunk 落到 Neo4j。

幂等：Document 按 document_id、Chunk 按确定性 chunk_id（document_id#chunk_index）MERGE，
重复入库不产生重复节点。每个 Chunk 保留来源位置（char_start/char_end/page/heading_path），
满足引用可追溯。
"""

from neo4j import Driver

from app.config import get_settings
from app.parsing.models import ParsedDocument
_INGEST = """
MERGE (d:Document {document_id: $document_id})
  SET d.source_path = $source_path,
      d.doc_type = $doc_type,
      d.name = $name,
      d.source_type = $source_type,
      d.parse_status = $parse_status,
      d.index_status = $index_status,
      d.chunk_count = $chunk_count
WITH d
UNWIND $rows AS row
  MERGE (c:Chunk {chunk_id: row.chunk_id})
    SET c.chunk_index = row.chunk_index,
        c.text = row.text,
        c.document_id = row.document_id,
        c.char_start = row.char_start,
        c.char_end = row.char_end,
        c.page = row.page,
        c.heading_path = row.heading_path,
        c.embedding = row.embedding
  MERGE (d)-[:HAS_CHUNK]->(c)
"""


def _file_name_from_path(path: str) -> str:
    """从路径取文件名作为 Document.name；取不到就回退原路径。"""
    try:
        from pathlib import Path

        return Path(path).name or path
    except Exception:  # noqa: BLE001 — 路径解析失败不影响写入
        return path


def _chunk_rows(doc: ParsedDocument, embeddings: list[list[float]]) -> list[dict]:
    """把 chunk 与其向量摊平成 UNWIND 行。"""
    rows = []
    for chunk, embedding in zip(doc.chunks, embeddings):
        loc = chunk.location
        rows.append(
            {
                "chunk_id": f"{doc.document_id}#{chunk.chunk_index}",
                "chunk_index": chunk.chunk_index,
                "text": chunk.text,
                "document_id": doc.document_id,
                "char_start": loc.char_start,
                "char_end": loc.char_end,
                "page": loc.page,
                "heading_path": loc.heading_path,
                "embedding": embedding,
            }
        )
    return rows


def ingest_document(
    driver: Driver,
    doc: ParsedDocument,
    embeddings: list[list[float]],
    *,
    name: str | None = None,
    source_type: str | None = None,
    parse_status: str = "parsed",
    index_status: str = "indexed",
    dim: int | None = None,
    database: str = "neo4j",
) -> int:
    """写入 Document 及其全部 Chunk（含 embedding），返回写入的 chunk 数。

    校验向量与 chunk 数量一致、且每个向量维度等于 dim（缺省取配置 embedding_dim），
    防止维度与向量索引不一致导致写入或后续查询失败。dim 须与 ensure_schema 一致。

    Document 节点顺带写入状态字段（name/source_type/parse_status/index_status/chunk_count），
    供 GET /api/documents 直接查图库返回前端徽标。name/source_type 缺省从 doc 推导。
    """
    if len(embeddings) != len(doc.chunks):
        raise ValueError(
            f"embeddings 数量({len(embeddings)})与 chunks 数量({len(doc.chunks)})不一致"
        )
    if dim is None:
        dim = get_settings().embedding_dim
    for i, vec in enumerate(embeddings):
        if len(vec) != dim:
            raise ValueError(f"第 {i} 个向量维度 {len(vec)} 不等于 EMBEDDING_DIM {dim}")

    if name is None:
        name = _file_name_from_path(doc.source_path)
    if source_type is None:
        source_type = doc.doc_type

    rows = _chunk_rows(doc, embeddings)
    driver.execute_query(
        _INGEST,
        document_id=doc.document_id,
        source_path=doc.source_path,
        doc_type=doc.doc_type,
        name=name,
        source_type=source_type,
        parse_status=parse_status,
        index_status=index_status,
        chunk_count=len(rows),
        rows=rows,
        database_=database,
    )
    return len(rows)
