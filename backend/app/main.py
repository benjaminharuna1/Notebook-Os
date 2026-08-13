from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.events import lifespan
from app.core.exceptions import register_exception_handlers


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    from app.features.auth.router import router as auth_router
    from app.features.settings.router import router as settings_router
    from app.features.ingestion.router import router as ingestion_router
    from app.features.documents.router import router as documents_router
    from app.features.search.router import router as search_router
    from app.features.chat.router import router as chat_router
    from app.features.models.router import router as models_router
    from app.features.graph.router import router as graph_router
    from app.features.skills.router import router as skills_router
    from app.features.projects.router import router as projects_router

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(settings_router, prefix="/api/v1")
    app.include_router(ingestion_router, prefix="/api/v1")
    app.include_router(documents_router, prefix="/api/v1")
    app.include_router(search_router, prefix="/api/v1")
    app.include_router(chat_router, prefix="/api/v1")
    app.include_router(models_router, prefix="/api/v1")
    app.include_router(graph_router, prefix="/api/v1")
    app.include_router(skills_router, prefix="/api/v1")
    app.include_router(projects_router, prefix="/api/v1")

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
