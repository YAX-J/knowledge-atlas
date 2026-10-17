from typing import Literal

from pydantic import BaseModel


class DependencyHealth(BaseModel):
    status: Literal["up", "down", "not_checked"]
    detail: str | None = None


class LivenessResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str


class ReadinessResponse(BaseModel):
    status: Literal["ready", "degraded"]
    dependencies: dict[str, DependencyHealth]

