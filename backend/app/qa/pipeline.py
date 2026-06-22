"""问答编排：embedding -> 向量召回 -> rerank -> 邻域扩展 -> 组装 -> LLM 生成带引用答案。

检索策略与上下文组装均在本层控制（不依赖第三方框架默认行为）。
只保留答案正文里真实出现的角标对应的 Citation，未被引用的 chunk 不计入。
"""

import logging
import re

from neo4j import Driver

from app.clients import llm
from app.graph.search import search_chunks
from app.qa.context import build_context
from app.qa.expand import expand_entities
from app.qa.models import Answer, Citation
from app.qa.prompt import build_answer_messages
from app.qa.rerank import rerank_chunks

logger = logging.getLogger(__name__)

_CITE_RE = re.compile(r"\[(\d+)\]")


def _used_indices(text: str) -> set[int]:
    """提取答案正文中实际出现的角标编号。"""
    return {int(n) for n in _CITE_RE.findall(text)}


def _confidence(used: set[int], total: int) -> str:
    """按被引用比例与数量给出粗略置信度。"""
    if not used:
        return "low"
    if len(used) >= 2:
        return "high"
    return "medium"


def answer_question(
    driver: Driver,
    question: str,
    *,
    top_k: int = 10,
    rerank_top_n: int = 5,
    database: str = "neo4j",
) -> Answer:
    """对问题做 GraphRAG 检索并生成带引用答案。"""
    query_embedding = llm.embed([question])[0]
    hits = search_chunks(driver, query_embedding, top_k=top_k, database=database)
    if not hits:
        return Answer(text="根据现有资料无法回答。", confidence="low", citations=[])

    reranked = rerank_chunks(question, hits, top_n=rerank_top_n)
    context_obj = expand_entities(
        driver, [h.chunk_id for h in reranked], database=database
    )
    context_str, citations = build_context(reranked, context_obj.paths)

    text = llm.chat(build_answer_messages(question, context_str))

    used = _used_indices(text)
    cited = [c for c in citations if c.index in used] if used else []
    return Answer(text=text, confidence=_confidence(used, len(citations)), citations=cited)
