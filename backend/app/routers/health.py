"""健康检查路由。"""

from fastapi import APIRouter, Request

from app.clients import llm
from app.clients.graph import verify_connectivity

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    """存活探针：不依赖任何外部服务，永远返回 ok。"""
    return {"status": "ok"}


@router.get("/health/deps")
async def health_deps(request: Request) -> dict:
    """依赖探针：探测 Neo4j 与 LLM 配置状态，任何失败都降级为文本，不抛 500。"""
    driver = request.app.state.neo4j
    try:
        verify_connectivity(driver)
        neo4j_status = "ok"
    except Exception as exc:  # noqa: BLE001 - 探针需吞掉所有异常，降级为文本
        neo4j_status = f"error: {exc}"

    llm_status = "configured" if llm.is_configured() else "not_configured"

    return {"neo4j": neo4j_status, "llm": llm_status}
