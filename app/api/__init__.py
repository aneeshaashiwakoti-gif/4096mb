"""API routes package for CodeImpact."""

from fastapi import APIRouter
from app.api.health import router as health_router
from app.api.impact import router as impact_router
from app.api.ask import router as ask_router
from app.api.fix import router as fix_router
from app.api.validation import router as validation_router
from app.api.project import router as project_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["Health"])
api_router.include_router(impact_router, prefix="/impact", tags=["Impact Analysis"])
api_router.include_router(ask_router, tags=["Assistant"])
api_router.include_router(fix_router, prefix="/fix", tags=["Fix Proposals"])
api_router.include_router(validation_router, tags=["Validation & Re-analysis"])
api_router.include_router(project_router, tags=["Projects"])

__all__ = ["api_router"]
