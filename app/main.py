import os
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request, Depends, Query
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.database import init_db, get_db, AsyncSessionLocal
from app.models.farmer import Farmer
from app.models.alert import AgriculturalAlert
from app.models.call import CallJob, CallLog
from app.models.scheme import GovernmentScheme
from app.services.market_service import MarketService
from app.services.news_service import NewsService
from app.services.firebase_service import FirebaseService
from app.api import api_router
from app.tasks.worker import run_weather_monitoring_cycle, run_market_monitoring_cycle

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("uzhavan_voice_app")

scheduler = AsyncIOScheduler()

async def scheduled_firebase_sync_job():
    """Periodic background sync to pull newly registered farmers from mobile app Firebase backend"""
    logger.info("⏱️ Running scheduled Firebase Mobile App farmer sync...")
    try:
        async with AsyncSessionLocal() as db:
            result = await FirebaseService.sync_app_registered_farmers(db)
            logger.info(f"📱 Scheduled Firebase sync result: {result}")
    except Exception as e:
        logger.error(f"Scheduled Firebase sync error: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize Database tables
    try:
        logger.info("🌱 Initializing Uzhavan AI Database tables...")
        await init_db()
    except Exception as e:
        logger.error(f"Database init warning: {e}")

    # Initial Sync: Fetch farmers already registered via Uzhavan AI Mobile App's Firebase backend
    if getattr(settings, "FIREBASE_SYNC_ON_STARTUP", True) and not os.getenv("VERCEL"):
        logger.info("📱 Syncing registered farmers from Uzhavan AI Mobile App's Firebase backend...")
        try:
            async with AsyncSessionLocal() as db:
                sync_result = await FirebaseService.sync_app_registered_farmers(db)
                logger.info(f"📱 Initial Firebase Farmer Sync result: {sync_result}")
        except Exception as e:
            logger.error(f"Initial Firebase sync error: {e}")

    # Start Autonomous Periodic Background Scheduler if not in serverless environment
    if not os.getenv("VERCEL"):
        logger.info("⏱️ Starting Autonomous Background Monitoring Scheduler...")
        scheduler.add_job(
            run_weather_monitoring_cycle,
            "interval",
            minutes=settings.WEATHER_CHECK_INTERVAL_MINUTES,
            id="auto_weather_job",
            replace_existing=True
        )
        scheduler.add_job(
            run_market_monitoring_cycle,
            "interval",
            minutes=settings.MARKET_CHECK_INTERVAL_MINUTES,
            id="auto_market_job",
            replace_existing=True
        )
        scheduler.add_job(
            scheduled_firebase_sync_job,
            "interval",
            minutes=settings.FIREBASE_SYNC_INTERVAL_MINUTES,
            id="auto_firebase_sync_job",
            replace_existing=True
        )
        scheduler.start()
    else:
        logger.info("⚡ Vercel Serverless environment detected: Disabling continuous interval background scheduler.")

    yield

    # Shutdown
    if scheduler.running:
        scheduler.shutdown()
    logger.info("Uzhavan AI Voice Portal stopped.")

app = FastAPI(
    title=settings.APP_NAME,
    description="Autonomous Multilingual Farmer Voice Communication System & Survey Portal",
    version="1.0.0",
    lifespan=lifespan
)

# Static and Templates (resolved with absolute paths)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(BASE_DIR, "static")
templates_dir = os.path.join(BASE_DIR, "templates")

if os.getenv("VERCEL"):
    tmp_audio_dir = "/tmp/audio"
    os.makedirs(tmp_audio_dir, exist_ok=True)
    app.mount("/static/audio", StaticFiles(directory=tmp_audio_dir), name="tmp_static_audio")

app.mount("/static", StaticFiles(directory=static_dir), name="static")
templates = Jinja2Templates(directory=templates_dir)

# Include API and Webhooks
app.include_router(api_router)

@app.get("/health")
@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "is_vercel": getattr(settings, "IS_VERCEL", False),
        "database": "sqlite-temporary" if getattr(settings, "IS_VERCEL", False) else "local-sqlite"
    }

# ------------------------------------------------------------------------------
# 10 MAIN PORTAL WEB SECTIONS
# ------------------------------------------------------------------------------

# 1. Dashboard
@app.get("/", response_class=HTMLResponse)
async def dashboard_page(
    request: Request,
    district: Optional[str] = Query(None),
    crop: Optional[str] = Query(None),
    language: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    from app.api.dashboard import get_dashboard_stats
    stats = await get_dashboard_stats(district=district, crop=crop, language=language, db=db)
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "active_page": "dashboard",
            "telephony_provider": settings.TELEPHONY_PROVIDER,
            "stats": stats,
            "district_filter": district,
            "crop_filter": crop,
            "lang_filter": language
        }
    )

# 2. Register Farmer Survey
@app.get("/register", response_class=HTMLResponse)
async def register_farmer_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="register.html",
        context={
            "active_page": "register",
            "telephony_provider": settings.TELEPHONY_PROVIDER
        }
    )

# 3. Farmers Management
@app.get("/farmers", response_class=HTMLResponse)
async def farmers_page(
    request: Request,
    search: Optional[str] = Query(None),
    district: Optional[str] = Query(None),
    crop: Optional[str] = Query(None),
    language: Optional[str] = Query(None),
    voice_status: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    from app.api.farmers import list_farmers
    farmers = await list_farmers(
        search=search,
        district=district,
        crop=crop,
        language=language,
        voice_status=voice_status,
        source=source,
        db=db
    )
    return templates.TemplateResponse(
        request=request,
        name="farmers.html",
        context={
            "active_page": "farmers",
            "telephony_provider": settings.TELEPHONY_PROVIDER,
            "farmers": farmers,
            "search": search,
            "district": district,
            "crop": crop,
            "language": language,
            "voice_status": voice_status,
            "source": source
        }
    )

# 4. Weather Alerts
@app.get("/weather-alerts", response_class=HTMLResponse)
async def weather_alerts_page(request: Request, db: AsyncSession = Depends(get_db)):
    stmt = select(AgriculturalAlert).where(AgriculturalAlert.alert_type == "WEATHER").order_by(AgriculturalAlert.id.desc())
    res = await db.execute(stmt)
    alerts = res.scalars().all()
    return templates.TemplateResponse(
        request=request,
        name="weather_alerts.html",
        context={
            "active_page": "weather",
            "telephony_provider": settings.TELEPHONY_PROVIDER,
            "alerts": alerts
        }
    )

# 5. Market Updates
@app.get("/market-updates", response_class=HTMLResponse)
async def market_updates_page(request: Request, crop: Optional[str] = Query(None)):
    prices = []
    try:
        prices = await MarketService.fetch_market_prices(crop=crop)
    except Exception as e:
        logger.error(f"Failed to fetch market prices for view: {e}")

    return templates.TemplateResponse(
        request=request,
        name="market_updates.html",
        context={
            "active_page": "market",
            "telephony_provider": settings.TELEPHONY_PROVIDER,
            "prices": prices,
            "crop_filter": crop
        }
    )

# 6. Government Schemes
@app.get("/schemes", response_class=HTMLResponse)
async def schemes_page(request: Request, db: AsyncSession = Depends(get_db)):
    from app.api.schemes import list_schemes
    schemes = await list_schemes(db=db)
    return templates.TemplateResponse(
        request=request,
        name="schemes.html",
        context={
            "active_page": "schemes",
            "telephony_provider": settings.TELEPHONY_PROVIDER,
            "schemes": schemes
        }
    )

# 7. Agricultural News
@app.get("/news", response_class=HTMLResponse)
async def news_page(request: Request):
    news_items = []
    try:
        news_items = await NewsService.fetch_agricultural_news()
    except Exception as e:
        logger.error(f"Failed to load news for view: {e}")

    return templates.TemplateResponse(
        request=request,
        name="news.html",
        context={
            "active_page": "news",
            "telephony_provider": settings.TELEPHONY_PROVIDER,
            "news": news_items
        }
    )

# 8. Voice Calls
@app.get("/voice-calls", response_class=HTMLResponse)
async def voice_calls_page(request: Request, db: AsyncSession = Depends(get_db)):
    stmt = select(CallJob).order_by(CallJob.id.desc())
    res = await db.execute(stmt)
    jobs = res.scalars().all()
    return templates.TemplateResponse(
        request=request,
        name="voice_calls.html",
        context={
            "active_page": "calls",
            "telephony_provider": settings.TELEPHONY_PROVIDER,
            "concurrency_limit": settings.TELEPHONY_CONCURRENCY_LIMIT,
            "jobs": jobs
        }
    )

# 9. Call History
@app.get("/call-history", response_class=HTMLResponse)
async def call_history_page(
    request: Request,
    status: Optional[str] = Query(None),
    call_type: Optional[str] = Query(None),
    language: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    from app.api.calls import get_call_history
    calls = await get_call_history(status=status, call_type=call_type, language=language, db=db)
    return templates.TemplateResponse(
        request=request,
        name="call_history.html",
        context={
            "active_page": "history",
            "telephony_provider": settings.TELEPHONY_PROVIDER,
            "calls": calls,
            "status": status,
            "call_type": call_type,
            "language": language
        }
    )

# 10. Settings
@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="settings.html",
        context={
            "active_page": "settings",
            "telephony_provider": settings.TELEPHONY_PROVIDER,
            "settings": settings,
            "firebase_status": FirebaseService.get_sync_status()
        }
    )
