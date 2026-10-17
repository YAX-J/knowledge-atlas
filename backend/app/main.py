from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError

from app.api.router import api_router
from app.core.config import get_settings
from app.core.errors import (
    AppError,
    app_error_handler,
    database_error_handler,
    validation_error_handler,
)
from app.core.logging import configure_logging
from app.core.middleware import RequestIdMiddleware


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.app_env)
    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Evidence-first personal developer knowledge graph API",
    )
    application.add_middleware(RequestIdMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.add_exception_handler(AppError, app_error_handler)
    application.add_exception_handler(RequestValidationError, validation_error_handler)
    application.add_exception_handler(SQLAlchemyError, database_error_handler)
    application.include_router(api_router, prefix=settings.api_v1_prefix)
    return application


app = create_app()

