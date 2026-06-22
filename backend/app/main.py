"""FastAPI 应用入口：装配日志、异常处理、路由，并用 lifespan 管理 Neo4j 驱动。"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.clients.graph import close, get_driver
from app.errors import register_exception_handlers
from app.graph import ensure_schema
from app.logging_conf import setup_logging
from app.routers.chat import router as chat_router
from app.routers.health import router as health_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时建 Neo4j 驱动并确保 schema，关闭时释放。

    ensure_schema 幂等；Neo4j 不可用时仅告警、不阻断启动，与 /health/deps 的降级哲学一致。
    """
    app.state.neo4j = get_driver()
    try:
        ensure_schema(app.state.neo4j)
    except Exception as exc:  # noqa: BLE001 — 依赖不可用不应阻断启动
        logger.warning("ensure_schema 失败（Neo4j 可能未就绪）：%s", exc)
    try:
        yield
    finally:
        close(app.state.neo4j)


def create_app() -> FastAPI:
    setup_logging()
    app = FastAPI(title="GraphRAG KG Agent API", lifespan=lifespan)
    register_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(chat_router)
    return app


app = create_app()
