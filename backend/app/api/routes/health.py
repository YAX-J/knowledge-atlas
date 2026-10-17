from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.dependencies import DatabaseSession
from app.core.config import get_settings
from app.schemas.health import DependencyHealth, LivenessResponse, ReadinessResponse


router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model=LivenessResponse)
def liveness() -> LivenessResponse:
    settings = get_settings()
    return LivenessResponse(service=settings.app_name)


@router.get("/ready", response_model=ReadinessResponse)
def readiness(db: DatabaseSession):
    dependencies: dict[str, DependencyHealth] = {}

    try:
        db.execute(text("SELECT 1"))
        dependencies["postgresql"] = DependencyHealth(status="up")
    except SQLAlchemyError:
        dependencies["postgresql"] = DependencyHealth(
            status="down", detail="database connection failed"
        )

    is_ready = all(
        dependency.status == "up"
        for dependency in dependencies.values()
    )
    response = ReadinessResponse(
        status="ready" if is_ready else "degraded",
        dependencies=dependencies,
    )
    if is_ready:
        return response
    return JSONResponse(status_code=503, content=response.model_dump(mode="json"))

