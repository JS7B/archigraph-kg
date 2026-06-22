"""expand_entities 集成：写 Chunk+Entity+MENTIONS+RELATES，验邻域扩展与证据回链。"""

from app.qa.expand import expand_entities

DOC = "test_expand"


def _seed(driver):
    """构造：chunk0 提及实体 A，A -[依赖]-> B（证据 chunk0）。"""
    driver.execute_query(
        """
        MERGE (c:Chunk {chunk_id: $cid})
          SET c.document_id = $doc
        MERGE (a:Entity {entity_id: $aid})
          SET a.name = 'A', a.document_id = $doc
        MERGE (b:Entity {entity_id: $bid})
          SET b.name = 'B', b.document_id = $doc
        MERGE (c)-[:MENTIONS]->(a)
        MERGE (a)-[:RELATES {type: '依赖', evidence_chunk_id: $cid}]->(b)
        """,
        cid=f"{DOC}#0", doc=DOC, aid=f"{DOC}::a::T", bid=f"{DOC}::b::T",
        database_="neo4j",
    )


def test_expand_returns_relation_path(ensured_schema):
    _seed(ensured_schema)
    ctx = expand_entities(ensured_schema, [f"{DOC}#0"])
    assert len(ctx.paths) == 1
    path = ctx.paths[0]
    assert path.source_name == "A"
    assert path.target_name == "B"
    assert path.type == "依赖"
    assert path.evidence_chunk_id == f"{DOC}#0"


def test_empty_chunk_ids_returns_empty(ensured_schema):
    ctx = expand_entities(ensured_schema, [])
    assert ctx.paths == []
