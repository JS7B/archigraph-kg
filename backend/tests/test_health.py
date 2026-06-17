"""健康检查路由测试。TestClient 会触发 lifespan；/health/deps 在 Neo4j 不可用时也不应抛错。"""

from fastapi.testclient import TestClient

from app.main import app


def test_health_ok():
    with TestClient(app) as client:
        resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_health_deps_structure():
    with TestClient(app) as client:
        resp = client.get("/health/deps")
    assert resp.status_code == 200
    body = resp.json()
    assert "neo4j" in body
    assert "llm" in body
