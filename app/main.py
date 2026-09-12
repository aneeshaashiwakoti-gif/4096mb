"""Main FastAPI Application Entrypoint for CodeImpact Person 3 Backend."""

from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import api_router
from app.config import settings
from app.utils.errors import register_error_handlers
from app.utils.logging import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle hooks."""
    logger.info(
        f"Starting CodeImpact Backend v1.0.0 (DEMO_MODE={settings.DEMO_MODE}, LLM_PROVIDER={settings.LLM_PROVIDER})"
    )
    yield
    logger.info("Shutting down CodeImpact Backend.")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    app = FastAPI(
        title="CodeImpact Backend & AI Reasoning Engine",
        description=(
            "Person 3's backend module for CodeImpact developer intelligence platform. "
            "Provides semantic impact explanation, deterministic risk scoring, "
            "citation verification, and safe fix proposals."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )

    # Configure CORS for Person 4 (Frontend)
    cors_origins = settings.get_cors_origins()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register error handlers
    register_error_handlers(app)

    # Register API routes
    app.include_router(api_router)

    # The Vite build is optional for API-only deployments. When it is present,
    # host the existing Sentinel frontend from the same localhost origin so the
    # browser can open the application directly at http://127.0.0.1:8000/.
    frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
    if frontend_dist.is_dir():
        app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
