import os
from celery import Celery
from app.config import settings

# Celery Application instance
celery_app = Celery(
    "uzhavan_voice_tasks",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.worker"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_track_started=True,
    worker_concurrency=settings.TELEPHONY_CONCURRENCY_LIMIT,
    task_routes={
        "app.tasks.worker.process_call_job_task": {"queue": "voice_calls"},
        "app.tasks.worker.autonomous_weather_monitor_task": {"queue": "monitors"},
        "app.tasks.worker.autonomous_market_monitor_task": {"queue": "monitors"},
        "app.tasks.worker.autonomous_scheme_monitor_task": {"queue": "monitors"},
        "app.tasks.worker.autonomous_news_monitor_task": {"queue": "monitors"},
        "app.tasks.worker.sync_firebase_farmers_task": {"queue": "sync"}
    },
    beat_schedule={
        "weather-monitor-periodic": {
            "task": "app.tasks.worker.autonomous_weather_monitor_task",
            "schedule": float(settings.WEATHER_CHECK_INTERVAL_MINUTES * 60)
        },
        "market-monitor-periodic": {
            "task": "app.tasks.worker.autonomous_market_monitor_task",
            "schedule": float(settings.MARKET_CHECK_INTERVAL_MINUTES * 60)
        },
        "scheme-monitor-periodic": {
            "task": "app.tasks.worker.autonomous_scheme_monitor_task",
            "schedule": float(settings.SCHEME_CHECK_INTERVAL_MINUTES * 60)
        },
        "news-monitor-periodic": {
            "task": "app.tasks.worker.autonomous_news_monitor_task",
            "schedule": float(settings.NEWS_CHECK_INTERVAL_MINUTES * 60)
        },
        "firebase-sync-periodic": {
            "task": "app.tasks.worker.sync_firebase_farmers_task",
            "schedule": float(settings.FIREBASE_SYNC_INTERVAL_MINUTES * 60)
        }
    }
)
