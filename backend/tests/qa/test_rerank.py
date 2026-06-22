"""rerank_chunks：按 reranker 返回顺序重排截断；空输入与失败回退。"""

from app.graph.search import ChunkHit
from app.qa import rerank as rerank_mod
from app.qa.rerank import rerank_chunks


def _hit(i: int, score: float) -> ChunkHit:
    return ChunkHit(
        chunk_id=f"d#{i}", document_id="d", chunk_index=i, text=f"t{i}",
        char_start=0, char_end=1, score=score,
    )


def test_reranks_by_returned_order(monkeypatch):
    chunks = [_hit(0, 0.9), _hit(1, 0.8), _hit(2, 0.7)]
    # reranker 认为 index 2 最相关，其次 0
    monkeypatch.setattr(
        rerank_mod.llm, "rerank", lambda q, docs, top_n=None: [(2, 0.99), (0, 0.5)]
    )
    out = rerank_chunks("q", chunks, top_n=2)
    assert [c.chunk_index for c in out] == [2, 0]


def test_empty_input_returns_empty():
    assert rerank_chunks("q", [], top_n=5) == []


def test_failure_falls_back_to_vector_order(monkeypatch):
    chunks = [_hit(0, 0.9), _hit(1, 0.8), _hit(2, 0.7)]

    def boom(q, docs, top_n=None):
        raise RuntimeError("rerank down")

    monkeypatch.setattr(rerank_mod.llm, "rerank", boom)
    out = rerank_chunks("q", chunks, top_n=2)
    assert [c.chunk_index for c in out] == [0, 1]  # 原序前 2
