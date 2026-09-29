from fastapi import APIRouter
from app.api.farmers import router as farmers_router
from app.api.alerts import router as alerts_router
from app.api.market import router as market_router
from app.api.schemes import router as schemes_router
from app.api.news import router as news_router
from app.api.calls import router as calls_router
from app.api.webhooks import router as webhooks_router
from app.api.dashboard import router as dashboard_router
from app.api.firebase import router as firebase_router

api_router = APIRouter()
api_router.include_router(farmers_router)
api_router.include_router(alerts_router)
api_router.include_router(market_router)
api_router.include_router(schemes_router)
api_router.include_router(news_router)
api_router.include_router(calls_router)
api_router.include_router(webhooks_router)
api_router.include_router(dashboard_router)
api_router.include_router(firebase_router)

__all__ = ["api_router"]
