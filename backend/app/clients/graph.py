"""Neo4j 驱动薄封装：建驱动、连通性探测、关闭。"""

import logging

from neo4j import Driver, GraphDatabase

from app.config import get_settings

logger = logging.getLogger(__name__)


def get_driver() -> Driver:
    """根据配置创建 Neo4j 驱动。"""
    settings = get_settings()
    return GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_username, settings.neo4j_password),
    )


def verify_connectivity(driver: Driver) -> bool:
    """执行 `RETURN 1` 探测连通性，成功返回 True，失败向上抛异常。"""
    records, _, _ = driver.execute_query("RETURN 1")
    return records[0][0] == 1


def close(driver: Driver) -> None:
    """关闭驱动，释放连接池。"""
    driver.close()
