"""embedding 编排：把已切好的 chunk 文本批量转成向量，与 chunk 严格同序。

复用 clients.llm.embed（OpenAI-compatible）。分批仅为绕开 embedding API 的单请求条数/
token 上限，不影响顺序：逐批结果按序拼接，输出第 i 个向量对应 doc.chunks[i]。
"""

from app.clients import llm
from app.parsing.models import ParsedDocument


def embed_chunks(doc: ParsedDocument, *, batch_size: int = 64) -> list[list[float]]:
    """对文档所有 chunk 文本生成向量，返回与 doc.chunks 同序的向量列表。"""
    texts = [chunk.text for chunk in doc.chunks]
    embeddings: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        embeddings.extend(llm.embed(texts[start : start + batch_size]))
    return embeddings
