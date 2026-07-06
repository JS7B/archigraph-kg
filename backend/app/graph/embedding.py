"""embedding 编排：把文本批量转成向量。

embed_texts 是通用版本（任意文本列表）；embed_chunks 是它的文档特化封装，
保留与 chunk 严格同序的约定。复用 clients.llm.embed（OpenAI-compatible）。

上下文增强：embed_chunks 向量化的不是裸 chunk.text，而是拼上「文档标题 +
heading_path」前缀的文本——否则用户按文档标题提问时向量检索召不回对应 chunk。
前缀只进向量，Chunk 节点存的 text 仍是原文（见 graph/writer.py）。
"""

from pathlib import Path

from app.clients import llm
from app.config import get_settings
from app.parsing.models import Chunk, ParsedDocument


def embed_texts(texts: list[str], *, batch_size: int = 64) -> list[list[float]]:
    """对任意文本列表批量生成向量，返回与输入同序的向量列表。

    分批仅为绕开 embedding API 的单请求条数/token 上限，不影响顺序。
    首向量维度校验：若与 EMBEDDING_DIM 配置不符立即抛错，避免维度错误延迟到
    写入/查询才暴露（L6 同类症状：换模型忘改 EMBEDDING_DIM）。
    """
    embeddings: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        embeddings.extend(llm.embed(texts[start : start + batch_size]))

    if embeddings:
        expected = get_settings().embedding_dim
        actual = len(embeddings[0])
        if actual != expected:
            raise ValueError(
                f"embedding 维度 {actual} 与配置 EMBEDDING_DIM={expected} 不符，"
                f"请检查 EMBEDDING_MODEL 与 EMBEDDING_DIM 是否一致"
            )
    return embeddings


def build_contextual_text(chunk: Chunk, title: str) -> str:
    """构造用于向量化的上下文增强文本：标题 + heading_path 前缀 + 原文。

    只影响 embedding 语义，不改变 chunk.text 本身。heading_path 为空时只拼标题。
    """
    context_parts = [title.strip()] if title and title.strip() else []
    if chunk.location.heading_path:
        context_parts.append(" > ".join(chunk.location.heading_path))
    if not context_parts:
        return chunk.text
    return "\n".join(context_parts) + "\n\n" + chunk.text


def embed_chunks(
    doc: ParsedDocument, *, title: str | None = None, batch_size: int = 64
) -> list[list[float]]:
    """对文档所有 chunk 生成向量（含标题/heading 上下文前缀），与 doc.chunks 同序。

    title 缺省从 source_path 取文件名；但 run_ingest 走临时文件解析，source_path
    是随机临时路径，调用方必须显式传真实文件名，否则前缀是无意义的 tmp 名。
    """
    if title is None:
        title = Path(doc.source_path).name or doc.source_path
    return embed_texts(
        [build_contextual_text(chunk, title) for chunk in doc.chunks],
        batch_size=batch_size,
    )
