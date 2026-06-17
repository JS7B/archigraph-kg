"""统一错误响应结构与全局异常处理器。"""

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ErrorDetail(BaseModel):
    type: str
    message: str


class ErrorResponse(BaseModel):
    """统一错误响应：{"error": {"type": ..., "message": ...}}"""

    error: ErrorDetail


def _payload(type_: str, message: str) -> dict:
    return ErrorResponse(error=ErrorDetail(type=type_, message=message)).model_dump()


def register_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器，保证所有错误返回统一结构。"""

    @app.exception_handler(HTTPException)
    async def _http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_payload("http_error", str(exc.detail)),
        )

    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=_payload("internal_error", str(exc)),
        )
