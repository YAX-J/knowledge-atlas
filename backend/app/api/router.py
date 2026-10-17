from fastapi import APIRouter

from app.api.routes import health, projects, sources, tasks


api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(projects.router)
api_router.include_router(sources.router)
api_router.include_router(tasks.router)

