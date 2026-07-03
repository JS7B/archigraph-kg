"""图谱查询路由（前端 P3）：实体列表、邻域、搜索。

返回前端 GraphData 结构：nodes [{id,name,type,documentId}] + edges [{source,target,type,confidence}]。
直接查 Neo4j Entity/RELATES，供图谱可视化视图消费。
"""

from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter(prefix="/api/graph", tags=["graph"])

_LIST_ENTITIES = """
MATCH (e:Entity)
WITH e, COUNT { (e)-[:RELATES]-() } + COUNT { (:Chunk)-[:MENTIONS]->(e) } AS degree
RETURN e.entity_id AS entity_id, e.name AS name, e.entity_type AS entity_type,
       e.document_id AS document_id, e.mention_count AS mention_count, degree
ORDER BY degree DESC, e.name
LIMIT $limit
"""

_LIST_EDGES = """
MATCH (s:Entity)-[r:RELATES]->(t:Entity)
RETURN s.entity_id AS source, t.entity_id AS target, r.type AS type,
       r.confidence AS confidence
LIMIT $limit
"""

_NEIGHBORS = """
MATCH (center:Entity {entity_id: $entity_id})
OPTIONAL MATCH (center)-[r1]-(nbr:Entity)
WITH center, collect(DISTINCT nbr) AS neighbors
UNWIND CASE WHEN size(neighbors)=0 THEN [center] ELSE neighbors + [center] END AS n
WITH collect(DISTINCT n) AS all_nodes
UNWIND all_nodes AS node
OPTIONAL MATCH (a)-[r:RELATES]->(b)
  WHERE a IN all_nodes AND b IN all_nodes
RETURN collect(DISTINCT {
  entity_id: node.entity_id, name: node.name,
  entity_type: node.entity_type, document_id: node.document_id
}) AS nodes,
       collect(DISTINCT {
  source: startNode(r).entity_id, target: endNode(r).entity_id,
  type: r.type, confidence: r.confidence
}) AS edges
"""

_SEARCH = """
MATCH (e:Entity)
WHERE toLower(e.name) CONTAINS toLower($q) OR toLower(e.normalized_name) CONTAINS toLower($q)
RETURN e.entity_id AS entity_id, e.name AS name, e.entity_type AS entity_type,
       e.document_id AS document_id
ORDER BY e.name
LIMIT $limit
"""


def _node(row: dict) -> dict:
    node = {
        "id": row["entity_id"],
        "name": row["name"] or "",
        "type": row["entity_type"] or "",
        "documentId": row["document_id"] or "",
    }
    # 列表查询附带的重要性数据（供前端分级展示）；search/neighbors 不返回这两列。
    if "degree" in row:
        node["degree"] = row["degree"] or 0
    if "mention_count" in row:
        node["mentionCount"] = row["mention_count"] or 0
    return node


def _edge(row: dict) -> dict:
    return {
        "source": row["source"],
        "target": row["target"],
        "type": row["type"] or "",
        "confidence": row.get("confidence"),
    }


@router.get("/entities")
async def list_entities(
    request: Request, limit: int = Query(100, ge=1, le=1000)
) -> dict:
    """返回实体列表与它们之间的 RELATES 边（前端 GraphData）。"""
    driver = request.app.state.neo4j
    ent_records, _, _ = driver.execute_query(
        _LIST_ENTITIES, limit=limit, database_="neo4j"
    )
    edge_records, _, _ = driver.execute_query(
        _LIST_EDGES, limit=limit * 2, database_="neo4j"
    )
    entity_ids = {r["entity_id"] for r in ent_records}
    return {
        "nodes": [_node(r.data()) for r in ent_records],
        # 只保留两端都在当前实体集内的边，避免 limit 截断后出现悬空边
        "edges": [
            _edge(r.data())
            for r in edge_records
            if r["source"] in entity_ids and r["target"] in entity_ids
        ],
    }


@router.get("/entities/{entity_id}/neighbors")
async def get_neighbors(request: Request, entity_id: str) -> dict:
    """返回单个实体的 1 跳邻域（含中心节点）。"""
    driver = request.app.state.neo4j
    records, _, _ = driver.execute_query(
        _NEIGHBORS, entity_id=entity_id, database_="neo4j"
    )
    if not records or not records[0]["nodes"]:
        raise HTTPException(status_code=404, detail=f"实体不存在: {entity_id}")
    row = records[0]
    # 过滤 None（OPTIONAL MATCH 在无边时产生 null 边）
    edges = [e for e in row["edges"] if e and e.get("source") and e.get("target")]
    return {
        "nodes": [
            {
                "id": n["entity_id"],
                "name": n["name"] or "",
                "type": n["entity_type"] or "",
                "documentId": n["document_id"] or "",
            }
            for n in row["nodes"]
            if n and n.get("entity_id")
        ],
        "edges": [
            {
                "source": e["source"],
                "target": e["target"],
                "type": e["type"] or "",
                "confidence": e.get("confidence"),
            }
            for e in edges
        ],
    }


@router.get("/search")
async def search_entities(
    request: Request, q: str = Query(..., min_length=1), limit: int = Query(20, ge=1, le=100)
) -> list[dict]:
    """实体名称模糊搜索（name 或 normalized_name CONTAINS q，大小写不敏感）。"""
    driver = request.app.state.neo4j
    records, _, _ = driver.execute_query(
        _SEARCH, q=q, limit=limit, database_="neo4j"
    )
    return [_node(r.data()) for r in records]
