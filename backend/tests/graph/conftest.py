"""图谱集成测试夹具：连真实 Neo4j 容器，连不上则跳过。

测试数据 document_id 一律以 'test_' 前缀，autouse 夹具在每个测试后清理。
向量索引名固定（与生产同名），但测试用 TEST_DIM=8 的小维度，故 ensured_schema
先 DROP 再以测试维度重建——这是「同容器同库跨 worktree 共享」约定下的必要代价。
"""

import pytest

from app.clients.graph import close, get_driver, verify_connectivity
from app.graph.schema import CHUNK_VECTOR_INDEX, ensure_schema

TEST_DIM = 8


@pytest.fixture(scope="session")
def neo4j_driver():
    driver = get_driver()
    try:
        verify_connectivity(driver)
    except Exception:
        close(driver)
        pytest.skip("Neo4j 不可用，跳过图谱集成测试")
    yield driver
    close(driver)


@pytest.fixture(scope="session")
def ensured_schema(neo4j_driver):
    """以测试维度重建向量索引并建约束。"""
    neo4j_driver.execute_query(
        f"DROP INDEX {CHUNK_VECTOR_INDEX} IF EXISTS", database_="neo4j"
    )
    ensure_schema(neo4j_driver, dim=TEST_DIM)
    return neo4j_driver


@pytest.fixture(autouse=True)
def _clean(neo4j_driver):
    yield
    neo4j_driver.execute_query(
        "MATCH (n) WHERE n.document_id STARTS WITH 'test_' DETACH DELETE n",
        database_="neo4j",
    )
