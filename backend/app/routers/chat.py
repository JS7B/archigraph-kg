"""问答路由：POST /api/chat 生成带引用答案；GET /api/chunks/{id} 反查引用原文。

响应用 model_dump(by_alias=True) 输出前端期望的 camelCase。
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.qa import answer_question

router = APIRouter(prefix="/api", tags=["qa"])


class ChatRequest(BaseModel):
    question: str


_CHUNK_QUERY = """
MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk {chunk_id: $chunk_id})
RETURN c.chunk_id AS chunk_id, d.source_path AS document_name,
       c.page AS page, c.char_start AS char_start, c.char_end AS char_end,
       c.heading_path AS heading_path, c.text AS text
"""


@router.post("/chat")
async def chat(request: Request, body: ChatRequest) -> dict:
    """对问题做 GraphRAG 检索并返回带引用答案。"""
    driver = request.app.state.neo4j
    answer = answer_question(driver, body.question)
    return answer.model_dump(by_alias=True)


@router.get("/chunks/{chunk_id}")
async def get_chunk(request: Request, chunk_id: str) -> dict:
    """按 chunk_id 反查原文，供前端展开引用。"""
    driver = request.app.state.neo4j
    records, _, _ = driver.execute_query(
        _CHUNK_QUERY, chunk_id=chunk_id, database_="neo4j"
    )
    if not records:
        raise HTTPException(status_code=404, detail=f"chunk 不存在: {chunk_id}")
    r = records[0]
    location_parts = []
    if r["page"] is not None:
        location_parts.append(f"第{r['page']}页")
    if r["heading_path"]:
        location_parts.append(" > ".join(r["heading_path"]))
    location_parts.append(f"字符 {r['char_start']}-{r['char_end']}")
    return {
        "chunkId": r["chunk_id"],
        "documentName": r["document_name"],
        "location": " · ".join(location_parts),
        "text": r["text"],
    }
