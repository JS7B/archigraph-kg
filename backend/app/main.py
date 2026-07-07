"""FastAPI 应用入口：装配日志、异常处理、路由，并用 lifespan 管理 Neo4j 驱动。"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.clients.graph import close, get_driver
from app.config import get_settings
from app.errors import register_exception_handlers
from app.graph import ensure_schema
from app.graph.schema import CHUNK_VECTOR_INDEX, MESSAGE_VECTOR_INDEX
from app.logging_conf import setup_logging
from app.routers.chat import router as chat_router
from app.routers.conversations import router as conversations_router
from app.routers.documents import router as documents_router
from app.routers.graph import router as graph_router
from app.routers.health import router as health_router
from app.routers.runs import router as runs_router
from app.runs import RunStore

logger = logging.getLogger(__name__)

# 两个向量索引的维度兜底常量（lifespan 启动校验用）
_CHUNK_INDEX = CHUNK_VECTOR_INDEX
_MESSAGE_INDEX = MESSAGE_VECTOR_INDEX


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时建 Neo4j 驱动并确保 schema，关闭时释放。

    ensure_schema 幂等；Neo4j 不可用时仅告警、不阻断启动，与 /health/deps 的降级哲学一致。
    RunStore 进程内常驻（不持久化），重启后历史 Run 丢失——前端刷新会重查 Document 状态。

    索引维度兜底（L6）：测试可能把共享索引重建为 TEST_DIM=8 且进程被强杀未恢复，
    此处在应用启动时校验维度，不匹配则 DROP+重建为生产维度，避免真实问答维度报错。
    """
    app.state.neo4j = get_driver()
    app.state.runs = RunStore()
    try:
        _ensure_vector_index_dim(app.state.neo4j, _CHUNK_INDEX)
        _ensure_vector_index_dim(app.state.neo4j, _MESSAGE_INDEX)
        ensure_schema(app.state.neo4j)
    except Exception as exc:  # noqa: BLE001 — 依赖不可用不应阻断启动
        logger.warning("ensure_schema 失败（Neo4j 可能未就绪）：%s", exc)
    try:
        yield
    finally:
        close(app.state.neo4j)


def _ensure_vector_index_dim(driver, index_name: str) -> None:
    """校验向量索引维度与配置一致；不一致（如测试残留 8 维）则 DROP（由后续 ensure_schema 重建）。

    根治 L6 兜底：测试强杀导致 8 维残留时，应用启动自动修正，真实问答不再撞维度。
    对 chunk / message 两个向量索引都调用。
    """
    from app.config import get_settings

    expected = get_settings().embedding_dim
    records, _, _ = driver.execute_query(
        "SHOW INDEXES YIELD name, type, options WHERE name=$name AND type='VECTOR' "
        "RETURN options",
        name=index_name,
        database_="neo4j",
    )
    if not records:
        return  # 索引不存在，交给 ensure_schema 创建
    actual_dim = records[0]["options"].get("indexConfig", {}).get("vector.dimensions")
    if actual_dim != expected:
        logger.warning(
            "向量索引 %s 维度 %s 与配置 %s 不符，DROP 重建（可能是测试残留）",
            index_name, actual_dim, expected,
        )
        driver.execute_query(f"DROP INDEX {index_name}", database_="neo4j")


def create_app() -> FastAPI:
    setup_logging()
    app = FastAPI(title="Archigraph API", lifespan=lifespan)
    register_exception_handlers(app)
    _register_middleware(app)
    app.include_router(health_router)
    app.include_router(chat_router)
    app.include_router(documents_router)
    app.include_router(conversations_router)
    app.include_router(runs_router)
    app.include_router(graph_router)
    return app


def _register_middleware(app: FastAPI) -> None:
    """装配中间件：CORS（限定来源）+ API Key 鉴权。

    注意 add_middleware 的执行顺序与添加顺序相反（后加的先执行）。这里鉴权加在
    CORS 之后，使鉴权在 CORS 处理之后生效；两者职责独立，顺序无强约束。
    """
    from fastapi.middleware.cors import CORSMiddleware

    from app.middleware import ApiKeyMiddleware

    settings = get_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()
        ],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(ApiKeyMiddleware)


app = create_app()
