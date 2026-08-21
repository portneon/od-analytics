from fastapi import APIRouter

from app.api.v1 import analytics, ask, auth, datasets, drilldown, executive, reports

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(executive.router)
api_router.include_router(datasets.router)
api_router.include_router(analytics.router)
api_router.include_router(drilldown.router)
api_router.include_router(ask.router)
api_router.include_router(reports.router)
