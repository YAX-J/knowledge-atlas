from fastapi import APIRouter

from app.api.routes import (
    agents,
    assistant,
    notes,
    graph,
    evolution,
    health,
    knowledge,
    projects,
    questions,
    repositories,
    retirement,
    search,
    sources,
    tasks,
    workspace,
    conversations,
)


api_router = APIRouter()
api_router.include_router(agents.router)
api_router.include_router(assistant.router)
api_router.include_router(notes.router)
api_router.include_router(health.router)
api_router.include_router(projects.router)
api_router.include_router(repositories.router)
api_router.include_router(sources.router)
api_router.include_router(tasks.router)
api_router.include_router(knowledge.router)
api_router.include_router(graph.router)
api_router.include_router(evolution.router)
api_router.include_router(retirement.router)
api_router.include_router(search.router)
api_router.include_router(questions.router)
api_router.include_router(workspace.router)
api_router.include_router(conversations.router)

