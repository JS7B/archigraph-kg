"""问答集成测试夹具：复用图谱板块的 Neo4j 探测、schema、清理逻辑。"""

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
        pytest.skip("Neo4j 不可用，跳过问答集成测试")
    yield driver
    close(driver)


@pytest.fixture(scope="session")
def ensured_schema(neo4j_driver):
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
