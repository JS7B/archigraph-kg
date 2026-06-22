"""reranker 重排：对召回的 chunk 按与问题的相关性重排并截断 top_n。

rerank 失败或空输入降级为按原向量 score 取前 top_n，不中断问答。
"""

import logging

from app.clients import llm
from app.graph.search import ChunkHit

logger = logging.getLogger(__name__)


def rerank_chunks(
    query: str, chunks: list[ChunkHit], *, top_n: int = 5
) -> list[ChunkHit]:
    """用 reranker 对 chunks 重排，返回相关性最高的 top_n 个。"""
    if not chunks:
        return []
    try:
        ranked = llm.rerank(query, [c.text for c in chunks], top_n=top_n)
        return [chunks[idx] for idx, _ in ranked]
    except Exception as exc:  # noqa: BLE001 - rerank 不可用时降级，不中断问答
        logger.warning("rerank 失败，回退按向量 score 排序：%s", exc)
        return chunks[:top_n]
