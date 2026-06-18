"""ensure_schema 后约束与向量索引应存在且索引 ONLINE。"""

from app.graph.schema import CHUNK_VECTOR_INDEX


def test_constraints_created(ensured_schema):
    records, _, _ = ensured_schema.execute_query(
        "SHOW CONSTRAINTS YIELD name RETURN name", database_="neo4j"
    )
    names = {r["name"] for r in records}
    assert "document_id_unique" in names
    assert "chunk_id_unique" in names


def test_vector_index_online(ensured_schema):
    records, _, _ = ensured_schema.execute_query(
        "SHOW INDEXES YIELD name, type, state RETURN name, type, state",
        database_="neo4j",
    )
    index = next((r for r in records if r["name"] == CHUNK_VECTOR_INDEX), None)
    assert index is not None
    assert index["type"] == "VECTOR"
    assert index["state"] == "ONLINE"
