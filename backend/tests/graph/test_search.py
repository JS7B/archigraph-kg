"""向量召回：top-k 顺序、score 降序、ChunkHit 字段完整（含 provenance）。"""

from app.graph.search import search_chunks
from app.graph.writer import ingest_document
from app.parsing.models import Chunk, ParsedDocument, SourceLocation
from tests.graph.conftest import TEST_DIM


def _onehot(i: int) -> list[float]:
    vec = [0.0] * TEST_DIM
    vec[i] = 1.0
    return vec


def _doc() -> ParsedDocument:
    raw = "AAABBBCCC"
    chunks = [
        Chunk(
            chunk_index=i,
            text=raw[i * 3 : i * 3 + 3],
            location=SourceLocation(
                document_id="test_search", char_start=i * 3, char_end=i * 3 + 3
            ),
            char_count=3,
        )
        for i in range(3)
    ]
    return ParsedDocument(
        document_id="test_search",
        source_path="test/s.txt",
        doc_type="text",
        raw_text=raw,
        chunks=chunks,
    )


def test_topk_returns_nearest_first(ensured_schema):
    ingest_document(
        ensured_schema, _doc(), [_onehot(0), _onehot(1), _onehot(2)], dim=TEST_DIM
    )
    query = [0.9, 0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    hits = search_chunks(ensured_schema, query, top_k=2)
    assert len(hits) == 2
    assert hits[0].chunk_index == 0
    assert hits[0].score >= hits[1].score


def test_hit_carries_provenance(ensured_schema):
    ingest_document(
        ensured_schema, _doc(), [_onehot(0), _onehot(1), _onehot(2)], dim=TEST_DIM
    )
    hits = search_chunks(ensured_schema, _onehot(2), top_k=1)
    hit = hits[0]
    assert hit.document_id == "test_search"
    assert hit.chunk_id == "test_search#2"
    assert hit.char_start == 6
    assert hit.char_end == 9
    assert hit.text == "CCC"
