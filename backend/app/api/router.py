from fastapi import APIRouter

from app.api.routes import graph, health, knowledge, projects, questions, search, sources, tasks


api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(projects.router)
api_router.include_router(sources.router)
api_router.include_router(tasks.router)
api_router.include_router(knowledge.router)
api_router.include_router(graph.router)
api_router.include_router(search.router)
api_router.include_router(questions.router)

