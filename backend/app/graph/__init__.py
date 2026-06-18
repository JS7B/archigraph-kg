"""图谱写入与向量检索层：schema 初始化、文档入库、向量召回。"""

from app.graph.embedding import embed_chunks
from app.graph.schema import CHUNK_VECTOR_INDEX, ensure_schema
from app.graph.search import ChunkHit, search_chunks
from app.graph.writer import ingest_document

__all__ = [
    "ensure_schema",
    "CHUNK_VECTOR_INDEX",
    "embed_chunks",
    "ingest_document",
    "search_chunks",
    "ChunkHit",
]
