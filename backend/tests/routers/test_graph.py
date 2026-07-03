"""graph 路由测试（P3 图谱查询）。

直接写真实 Entity/RELATES 节点，验证 entities 列表/neighbors 邻域/search 搜索。
"""

import pytest
from fastapi.testclient import TestClient

from app.clients.graph import get_driver
from app.main import create_app
from app.runs import RunStore


@pytest.fixture
def seeded_graph(ensured_schema):
    """写入测试用实体与关系：A --uses--> B，A --stores--> C。"""
    ensured_schema.execute_query(
        """
        MERGE (a:Entity {entity_id: 'test_ent_A'})
          SET a.name='Neo4j', a.entity_type='Database', a.document_id='test_g.md',
              a.normalized_name='neo4j'
        MERGE (b:Entity {entity_id: 'test_ent_B'})
          SET b.name='GraphRAG', b.entity_type='Method', b.document_id='test_g.md',
              b.normalized_name='graphrag'
        MERGE (c:Entity {entity_id: 'test_ent_C'})
          SET c.name='FastAPI', c.entity_type='Framework', c.document_id='test_g.md',
              c.normalized_name='fastapi'
        MERGE (a)-[:RELATES {type: 'uses', evidence_chunk_id: 'test_g.md#0', confidence: 0.9}]->(b)
        MERGE (a)-[:RELATES {type: 'stores', evidence_chunk_id: 'test_g.md#1', confidence: 0.8}]->(c)
        """,
        database_="neo4j",
    )
    yield ensured_schema
    ensured_schema.execute_query(
        "MATCH (e:Entity) WHERE e.entity_id STARTS WITH 'test_ent_' DETACH DELETE e",
        database_="neo4j",
    )


def _client():
    app = create_app()
    app.state.neo4j = get_driver()
    app.state.runs = RunStore()
    return TestClient(app)


def test_list_entities(seeded_graph):
    client = _client()
    # limit 拉满：共享库可能已有其它真实实体，避免种子实体被 LIMIT 截断挤出。
    r = client.get("/api/graph/entities?limit=1000")
    assert r.status_code == 200
    body = r.json()
    names = {n["name"] for n in body["nodes"]}
    assert {"Neo4j", "GraphRAG", "FastAPI"}.issubset(names)
    # 边的两端都在节点集内
    node_ids = {n["id"] for n in body["nodes"]}
    for e in body["edges"]:
        assert e["source"] in node_ids and e["target"] in node_ids
    # 测试实体的边
    test_edges = [
        e for e in body["edges"] if e["source"].startswith("test_ent_")
    ]
    assert len(test_edges) >= 2
    # B4：每个节点都带 degree / mentionCount 字段
    for n in body["nodes"]:
        assert "degree" in n and "mentionCount" in n
    # B4：整表按度数降序（直接验证 ORDER BY degree DESC，对任意数据都成立）
    degrees = [n["degree"] for n in body["nodes"]]
    assert degrees == sorted(degrees, reverse=True)
    # B4：A（2 条 RELATES）排在只有 1 条的 B、C 之前
    order = [n["id"] for n in body["nodes"] if n["id"].startswith("test_ent_")]
    assert order.index("test_ent_A") < order.index("test_ent_B")
    assert order.index("test_ent_A") < order.index("test_ent_C")


def test_neighbors(seeded_graph):
    client = _client()
    r = client.get("/api/graph/entities/test_ent_A/neighbors")
    assert r.status_code == 200
    body = r.json()
    ids = {n["id"] for n in body["nodes"]}
    # 中心 A + 邻居 B、C
    assert "test_ent_A" in ids
    assert "test_ent_B" in ids
    assert "test_ent_C" in ids
    assert len(body["edges"]) >= 2


def test_neighbors_missing_404(ensured_schema):
    client = _client()
    r = client.get("/api/graph/entities/test_ent_nope/neighbors")
    assert r.status_code == 404


def test_search(seeded_graph):
    client = _client()
    r = client.get("/api/graph/search?q=neo")
    assert r.status_code == 200
    results = r.json()
    assert any(x["id"] == "test_ent_A" for x in results)
    # 大小写不敏感
    r2 = client.get("/api/graph/search?q=GRAPH")
    assert any(x["id"] == "test_ent_B" for x in r2.json())


def test_search_empty_q_422(ensured_schema):
    client = _client()
    # min_length=1 约束：空串返回 422
    r = client.get("/api/graph/search?q=")
    assert r.status_code == 422
