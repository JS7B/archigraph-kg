import pytest

from app.clients.graph import close, get_driver, verify_connectivity
from app.config import get_settings


@pytest.fixture(autouse=True)
def _clean():
    """Override the repository-wide live cleanup for pure resolution tests."""

    yield


@pytest.fixture
def resolution_neo4j_driver():
    settings = get_settings()
    if not settings.neo4j_uri:
        pytest.skip("Neo4j configuration unavailable")
    driver = get_driver()
    try:
        verify_connectivity(driver)
    except Exception:
        close(driver)
        pytest.skip("Neo4j unavailable")
    yield driver
    driver.execute_query(
        "MATCH (n) WHERE n.document_id STARTS WITH 'test_resolution_' "
        "OR (n:CanonicalEntity AND n.canonical_name STARTS WITH 'test_resolution_') "
        "OR (n:CanonicalEntity AND "
        "n.canonical_id STARTS WITH 'canonical:test_resolution_guard:') "
        "DETACH DELETE n",
        database_="neo4j",
    )
    close(driver)
