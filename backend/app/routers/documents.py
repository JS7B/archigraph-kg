"""文档库路由：上传入库（同步链路）、列表、单文档详情。

A 板块（文档上传/入库 API）：POST 同步跑完整链路返回结果摘要；GET 直接查 Neo4j
Document 节点（写入时已落状态字段）。响应用 camelCase alias，与 chat 路由风格一致。
"""

import os
import tempfile

from fastapi import APIRouter, HTTPException, Request, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from app.config import get_settings
from app.extraction import extract_and_ingest
from app.graph import embed_chunks, ingest_document
from app.parsing import parse_file

router = APIRouter(prefix="/api", tags=["documents"])

# 支持的上传扩展名 → doc_type 映射（doc_type 喂给 parse_file 决定走哪个 parser）。
_SUPPORTED = {".md": "markdown", ".txt": "txt", ".pdf": "pdf"}


# ── 响应模型（camelCase alias 对齐前端契约，populate_by_name 便于内部构造）──

_RESPONSE_CONFIG = ConfigDict(populate_by_name=True)


class _ExtractionSummary(BaseModel):
    model_config = _RESPONSE_CONFIG

    entity_count: int = Field(alias="entityCount")
    relation_count: int = Field(alias="relationCount")
    mention_count: int = Field(alias="mentionCount")
    failed_chunks: int = Field(alias="failedChunks")


class IngestResponse(BaseModel):
    model_config = _RESPONSE_CONFIG

    document_id: str = Field(alias="documentId")
    document_name: str = Field(alias="documentName")
    chunk_count: int = Field(alias="chunkCount")
    extraction: _ExtractionSummary


class DocumentMeta(BaseModel):
    """前端 DocumentMeta：id/name/sourceType/parseStatus/indexStatus/chunkCount。"""

    model_config = _RESPONSE_CONFIG

    document_id: str = Field(alias="id")
    name: str
    source_type: str = Field(alias="sourceType")
    parse_status: str = Field(alias="parseStatus")
    index_status: str = Field(alias="indexStatus")
    chunk_count: int = Field(alias="chunkCount")


# ── Cypher：查 Document 节点（直接读写入时落的状态字段）──

_LIST_DOCS = """
MATCH (d:Document)
RETURN d.document_id AS document_id, d.name AS name, d.source_type AS source_type,
       d.parse_status AS parse_status, d.index_status AS index_status,
       d.chunk_count AS chunk_count
ORDER BY d.name
"""

_GET_DOC = """
MATCH (d:Document {document_id: $document_id})
RETURN d.document_id AS document_id, d.name AS name, d.source_type AS source_type,
       d.parse_status AS parse_status, d.index_status AS index_status,
       d.chunk_count AS chunk_count
"""


def _row_to_meta(row: dict) -> dict:
    """把 Cypher 行转成 DocumentMeta 的 camelCase dict。"""
    return DocumentMeta(
        document_id=row["document_id"],
        name=row["name"] or "",
        source_type=row["source_type"] or "",
        parse_status=row["parse_status"] or "pending",
        index_status=row["index_status"] or "pending",
        chunk_count=row["chunk_count"] or 0,
    ).model_dump(by_alias=True)


@router.post("/documents")
async def upload_document(request: Request, file: UploadFile) -> dict:
    """上传单文件并同步跑完整入库链路：解析→embedding→写图→抽取。

    document_id 沿用 parse_file 内部生成的稳定 id，保证 chunk_id 幂等。
    临时文件用 try/finally 确保无论成败都清理。
    """
    settings = get_settings()
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in _SUPPORTED:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型: {ext or '(无扩展名)'}，仅支持 {sorted(_SUPPORTED)}",
        )

    content = await file.read()
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"文件过大({len(content)}字节)，上限 {settings.max_upload_mb}MB",
        )

    driver = request.app.state.neo4j
    tmp_path: str | None = None
    try:
        # 写临时文件，让 parse_file 按真实文件读（PDF/Markdown 需文件句柄）。
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=ext, prefix="upload_"
        ) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        # document_id 用源文件名（非临时文件名），保证同文件重复上传幂等：
        # chunk_id = document_id#chunk_index，document_id 必须稳定。
        source_name = os.path.basename(file.filename or "upload")
        doc = parse_file(tmp_path, document_id=source_name)
        embeddings = embed_chunks(doc)
        # name/source_type 显式传源文件名与类型，避免 ingest_document 从临时路径推导出错。
        chunk_count = ingest_document(
            driver, doc, embeddings, name=source_name, source_type=_SUPPORTED[ext]
        )
        stats = extract_and_ingest(driver, doc)

        return IngestResponse(
            document_id=doc.document_id,
            document_name=os.path.basename(file.filename or doc.source_path),
            chunk_count=chunk_count,
            extraction=_ExtractionSummary(
                entity_count=stats.entity_count,
                relation_count=stats.relation_count,
                mention_count=stats.mention_count,
                failed_chunks=len(stats.failed_chunks),
            ),
        ).model_dump(by_alias=True)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:  # noqa: BLE001 — 清理失败不阻断主流程
                pass


@router.get("/documents")
async def list_documents(request: Request) -> list[dict]:
    """列出所有文档及其状态（直接查 Document 节点）。"""
    driver = request.app.state.neo4j
    records, _, _ = driver.execute_query(_LIST_DOCS, database_="neo4j")
    return [_row_to_meta(r.data()) for r in records]


@router.get("/documents/{document_id}")
async def get_document(request: Request, document_id: str) -> dict:
    """取单个文档详情。"""
    driver = request.app.state.neo4j
    records, _, _ = driver.execute_query(
        _GET_DOC, document_id=document_id, database_="neo4j"
    )
    if not records:
        raise HTTPException(status_code=404, detail=f"文档不存在: {document_id}")
    return _row_to_meta(records[0].data())
