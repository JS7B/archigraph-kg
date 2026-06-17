"""FastAPI 应用入口：装配日志、异常处理、路由，并用 lifespan 管理 Neo4j 驱动。"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.clients.graph import close, get_driver
from app.errors import register_exception_handlers
from app.logging_conf import setup_logging
from app.routers.health import router as health_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时建 Neo4j 驱动存入 app.state，关闭时释放。"""
    app.state.neo4j = get_driver()
    try:
        yield
    finally:
        close(app.state.neo4j)


def create_app() -> FastAPI:
    setup_logging()
    app = FastAPI(title="GraphRAG KG Agent API", lifespan=lifespan)
    register_exception_handlers(app)
    app.include_router(health_router)
    return app


app = create_app()
