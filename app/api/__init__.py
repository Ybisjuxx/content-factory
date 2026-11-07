from fastapi import APIRouter
from app.api.routes_jobs import router as jobs_router
from app.api.routes_assets import router as assets_router
from app.api.routes_system import router as system_router
from app.api.routes_trends import router as trends_router
from app.api.routes_distribution import router as distribution_router
from app.api.routes_moneyprinter import router as moneyprinter_router

api_router = APIRouter()
api_router.include_router(jobs_router)
api_router.include_router(assets_router)
api_router.include_router(system_router)
api_router.include_router(trends_router)
api_router.include_router(distribution_router)
api_router.include_router(moneyprinter_router)

__all__ = ["api_router"]
