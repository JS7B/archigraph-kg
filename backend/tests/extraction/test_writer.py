"""写图集成测试：先 ingest_document 建 Chunk，再 write_extraction，查回 MENTIONS/RELATES。"""

from app.extraction.models import DocumentExtraction, MergedEntity, MergedRelation
from app.extraction.writer import write_extraction
from app.graph.writer import ingest_document
from app.parsing.models import Chunk, ParsedDocument, SourceLocation
from tests.extraction.conftest import TEST_DIM

DOC_ID = "test_extr"


def _vec(seed: float) -> list[float]:
    return [seed] + [0.0] * (TEST_DIM - 1)


def _ingest_chunks(driver):
    """写入 2 个 Chunk，供 MENTIONS MATCH。"""
    chunks = [
        Chunk(
            chunk_index=i,
            text=f"chunk {i}",
            location=SourceLocation(document_id=DOC_ID, char_start=i, char_end=i + 1),
            char_count=1,
        )
        for i in range(2)
    ]
    doc = ParsedDocument(
        document_id=DOC_ID, source_path="x", doc_type="text", raw_text="xx", chunks=chunks
    )
    ingest_document(driver, doc, [_vec(1.0), _vec(2.0)], dim=TEST_DIM)


def _extraction() -> DocumentExtraction:
    return DocumentExtraction(
        entities=[
            MergedEntity(
                entity_id=f"{DOC_ID}::fastapi::技术概念",
                name="FastAPI",
                type="技术概念",
                normalized_name="fastapi",
                description="Web 框架",
                mention_chunk_ids=[f"{DOC_ID}#0", f"{DOC_ID}#1"],
            ),
            MergedEntity(
                entity_id=f"{DOC_ID}::pydantic::技术概念",
                name="Pydantic",
                type="技术概念",
                normalized_name="pydantic",
                description="",
                mention_chunk_ids=[f"{DOC_ID}#0"],
            ),
        ],
        relations=[
            MergedRelation(
                source_id=f"{DOC_ID}::fastapi::技术概念",
                target_id=f"{DOC_ID}::pydantic::技术概念",
                type="依赖",
                confidence=0.9,
                evidence_chunk_id=f"{DOC_ID}#0",
            )
        ],
    )


def test_write_counts(ensured_schema):
    _ingest_chunks(ensured_schema)
    n_ent, n_rel, n_men = write_extraction(ensured_schema, DOC_ID, _extraction())
    assert n_ent == 2
    assert n_rel == 1
    assert n_men == 3


def test_mentions_created(ensured_schema):
    _ingest_chunks(ensured_schema)
    write_extraction(ensured_schema, DOC_ID, _extraction())
    records, _, _ = ensured_schema.execute_query(
        "MATCH (c:Chunk)-[:MENTIONS]->(e:Entity {entity_id: $eid}) "
        "RETURN count(c) AS n",
        eid=f"{DOC_ID}::fastapi::技术概念",
        database_="neo4j",
    )
    assert records[0]["n"] == 2


def test_relation_properties_round_trip(ensured_schema):
    _ingest_chunks(ensured_schema)
    write_extraction(ensured_schema, DOC_ID, _extraction())
    records, _, _ = ensured_schema.execute_query(
        "MATCH (:Entity {entity_id: $s})-[r:RELATES]->(:Entity {entity_id: $t}) "
        "RETURN r.type AS type, r.confidence AS confidence, "
        "r.evidence_chunk_id AS evidence",
        s=f"{DOC_ID}::fastapi::技术概念",
        t=f"{DOC_ID}::pydantic::技术概念",
        database_="neo4j",
    )
    assert len(records) == 1
    assert records[0]["type"] == "依赖"
    assert records[0]["confidence"] == 0.9
    assert records[0]["evidence"] == f"{DOC_ID}#0"


def test_write_is_idempotent(ensured_schema):
    _ingest_chunks(ensured_schema)
    write_extraction(ensured_schema, DOC_ID, _extraction())
    write_extraction(ensured_schema, DOC_ID, _extraction())
    records, _, _ = ensured_schema.execute_query(
        "MATCH (e:Entity {document_id: $d}) RETURN count(e) AS n",
        d=DOC_ID,
        database_="neo4j",
    )
    assert records[0]["n"] == 2
    rel_records, _, _ = ensured_schema.execute_query(
        "MATCH (:Entity {document_id: $d})-[r:RELATES]->() RETURN count(r) AS n",
        d=DOC_ID,
        database_="neo4j",
    )
    assert rel_records[0]["n"] == 1
