"""ingest_document 写入计数、provenance 回读、幂等、维度校验。"""

import pytest

from app.graph.writer import ingest_document
from app.parsing.models import Chunk, ParsedDocument, SourceLocation
from tests.graph.conftest import TEST_DIM


def _vec(seed: float) -> list[float]:
    return [seed] + [0.0] * (TEST_DIM - 1)


def _doc(document_id: str = "test_doc1") -> ParsedDocument:
    raw = "第一段内容。第二段内容。"
    chunks = [
        Chunk(
            chunk_index=0,
            text="第一段内容。",
            location=SourceLocation(
                document_id=document_id, char_start=0, char_end=6, heading_path=["一级标题"]
            ),
            char_count=6,
        ),
        Chunk(
            chunk_index=1,
            text="第二段内容。",
            location=SourceLocation(
                document_id=document_id, char_start=6, char_end=12, page=2
            ),
            char_count=6,
        ),
    ]
    return ParsedDocument(
        document_id=document_id,
        source_path="test/doc1.md",
        doc_type="markdown",
        raw_text=raw,
        chunks=chunks,
    )


def test_ingest_returns_chunk_count(ensured_schema):
    doc = _doc()
    count = ingest_document(ensured_schema, doc, [_vec(1.0), _vec(2.0)], dim=TEST_DIM)
    assert count == 2


def test_chunk_provenance_round_trips(ensured_schema):
    doc = _doc()
    ingest_document(ensured_schema, doc, [_vec(1.0), _vec(2.0)], dim=TEST_DIM)
    records, _, _ = ensured_schema.execute_query(
        "MATCH (c:Chunk {chunk_id: 'test_doc1#0'}) "
        "RETURN c.document_id AS document_id, c.char_start AS char_start, "
        "c.char_end AS char_end, c.heading_path AS heading_path",
        database_="neo4j",
    )
    assert len(records) == 1
    row = records[0]
    assert row["document_id"] == "test_doc1"
    assert row["char_start"] == 0
    assert row["char_end"] == 6
    assert row["heading_path"] == ["一级标题"]


def test_has_chunk_relationship(ensured_schema):
    doc = _doc()
    ingest_document(ensured_schema, doc, [_vec(1.0), _vec(2.0)], dim=TEST_DIM)
    records, _, _ = ensured_schema.execute_query(
        "MATCH (:Document {document_id: 'test_doc1'})-[:HAS_CHUNK]->(c:Chunk) "
        "RETURN count(c) AS n",
        database_="neo4j",
    )
    assert records[0]["n"] == 2


def test_ingest_is_idempotent(ensured_schema):
    doc = _doc()
    ingest_document(ensured_schema, doc, [_vec(1.0), _vec(2.0)], dim=TEST_DIM)
    ingest_document(ensured_schema, doc, [_vec(1.0), _vec(2.0)], dim=TEST_DIM)
    records, _, _ = ensured_schema.execute_query(
        "MATCH (c:Chunk {document_id: 'test_doc1'}) RETURN count(c) AS n",
        database_="neo4j",
    )
    assert records[0]["n"] == 2


def test_embedding_count_mismatch_raises(ensured_schema):
    doc = _doc()
    with pytest.raises(ValueError):
        ingest_document(ensured_schema, doc, [_vec(1.0)], dim=TEST_DIM)


def test_embedding_dim_mismatch_raises(ensured_schema):
    doc = _doc()
    with pytest.raises(ValueError):
        ingest_document(ensured_schema, doc, [[1.0, 2.0], [3.0, 4.0]], dim=TEST_DIM)
