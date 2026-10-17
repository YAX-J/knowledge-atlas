from typing import Any

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError


class AppError(Exception):
    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


def error_payload(
    request: Request,
    *,
    code: str,
    message: str,
    details: Any = None,
) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
            "request_id": getattr(request.state, "request_id", None),
        }
    }


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(
            request,
            code=exc.code,
            message=exc.message,
            details=exc.details,
        ),
    )


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=jsonable_encoder(
            error_payload(
                request,
                code="INVALID_REQUEST",
                message="请求参数不符合接口约定",
                details={"errors": exc.errors()},
            )
        ),
    )


async def database_error_handler(
    request: Request, exc: SQLAlchemyError
) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content=error_payload(
            request,
            code="DATABASE_UNAVAILABLE",
            message="数据库暂时不可用",
        ),
    )

