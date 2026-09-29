import os
from datetime import datetime, time
from typing import Dict
from dotenv import load_dotenv

load_dotenv()

class Settings:
    APP_NAME: str = os.getenv("APP_NAME", "Uzhavan AI - Autonomous Voice Portal")
    APP_ENV: str = os.getenv("APP_ENV", "development")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "uzhavan_secret_key_2026")
    DEBUG: bool = os.getenv("DEBUG", "True").lower() in ("true", "1", "yes")
    PORT: int = int(os.getenv("PORT", "8000"))
    HOST: str = os.getenv("HOST", "0.0.0.0")

    # Base Webhook URL
    BASE_WEBHOOK_URL: str = os.getenv("BASE_WEBHOOK_URL", "http://localhost:8000")

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./uzhavan_voice.db")
    DATABASE_SYNC_URL: str = os.getenv("DATABASE_SYNC_URL", "sqlite:///./uzhavan_voice.db")

    # Live Uzhavan AI API Integration
    UZHAVAN_LIVE_API_BASE: str = os.getenv("UZHAVAN_LIVE_API_BASE", "https://uzhavan-ai.duckdns.org").rstrip("/")

    # Firebase Backend Integration (Uzhavan AI Mobile App)
    FIREBASE_PROJECT_ID: str = os.getenv("FIREBASE_PROJECT_ID", "uzhavan-ai-686d6")
    FIREBASE_API_KEY: str = os.getenv("FIREBASE_API_KEY", "AIzaSyDvfHQ3bAFbe2kvkkEQOkKeU0kgZcTZIH4")
    FIREBASE_AUTH_DOMAIN: str = os.getenv("FIREBASE_AUTH_DOMAIN", "uzhavan-ai-686d6.firebaseapp.com")
    FIREBASE_STORAGE_BUCKET: str = os.getenv("FIREBASE_STORAGE_BUCKET", "uzhavan-ai-686d6.firebasestorage.app")
    FIREBASE_SERVICE_ACCOUNT_KEY: str = os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY", "")
    FIREBASE_SYNC_INTERVAL_MINUTES: int = int(os.getenv("FIREBASE_SYNC_INTERVAL_MINUTES", "15"))
    FIREBASE_SYNC_ON_STARTUP: bool = os.getenv("FIREBASE_SYNC_ON_STARTUP", "True").lower() in ("true", "1", "yes")

    # Weather Provider
    WEATHER_PROVIDER: str = os.getenv("WEATHER_PROVIDER", "open-meteo")
    OPENWEATHER_API_KEY: str = os.getenv("OPENWEATHER_API_KEY", "")

    # Telephony
    TELEPHONY_PROVIDER: str = os.getenv("TELEPHONY_PROVIDER", "simulation").lower()
    TELEPHONY_CONCURRENCY_LIMIT: int = int(os.getenv("TELEPHONY_CONCURRENCY_LIMIT", "10"))

    # Exotel Credentials
    EXOTEL_ACCOUNT_SID: str = os.getenv("EXOTEL_ACCOUNT_SID", "")
    EXOTEL_API_KEY: str = os.getenv("EXOTEL_API_KEY", "")
    EXOTEL_API_TOKEN: str = os.getenv("EXOTEL_API_TOKEN", "")
    EXOTEL_CALLER_ID: str = os.getenv("EXOTEL_CALLER_ID", "")
    EXOTEL_SUBDOMAIN: str = os.getenv("EXOTEL_SUBDOMAIN", "api.exotel.com")

    # Twilio Credentials
    TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_PHONE_NUMBER: str = os.getenv("TWILIO_PHONE_NUMBER", "")

    # TTS Settings
    TTS_PROVIDER: str = os.getenv("TTS_PROVIDER", "uzhavan-live")

    # Queue & Celery
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    USE_CELERY: bool = os.getenv("USE_CELERY", "False").lower() in ("true", "1", "yes")

    # Retry System
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
    RETRY_DELAY_MINUTES: int = int(os.getenv("RETRY_DELAY_MINUTES", "30"))

    # Quiet Hours
    QUIET_HOURS_START: int = int(os.getenv("QUIET_HOURS_START", "21")) # 21:00 (9 PM)
    QUIET_HOURS_END: int = int(os.getenv("QUIET_HOURS_END", "6"))      # 06:00 (6 AM)
    EMERGENCY_OVERRIDE_QUIET_HOURS: bool = os.getenv("EMERGENCY_OVERRIDE_QUIET_HOURS", "True").lower() in ("true", "1", "yes")

    # Monitoring Intervals (Minutes)
    WEATHER_CHECK_INTERVAL_MINUTES: int = int(os.getenv("WEATHER_CHECK_INTERVAL_MINUTES", "30"))
    MARKET_CHECK_INTERVAL_MINUTES: int = int(os.getenv("MARKET_CHECK_INTERVAL_MINUTES", "60"))
    SCHEME_CHECK_INTERVAL_MINUTES: int = int(os.getenv("SCHEME_CHECK_INTERVAL_MINUTES", "120"))
    NEWS_CHECK_INTERVAL_MINUTES: int = int(os.getenv("NEWS_CHECK_INTERVAL_MINUTES", "60"))

    # Supported Languages Mapping
    SUPPORTED_LANGUAGES: Dict[str, Dict[str, str]] = {
        "ta-IN": {
            "name": "Tamil",
            "native": "தமிழ்",
            "tts_code": "ta",
            "gcp_code": "ta-IN",
        },
        "en-IN": {
            "name": "English",
            "native": "English",
            "tts_code": "en",
            "gcp_code": "en-IN",
        },
        "te-IN": {
            "name": "Telugu",
            "native": "తెలుగు",
            "tts_code": "te",
            "gcp_code": "te-IN",
        },
        "kn-IN": {
            "name": "Kannada",
            "native": "ಕನ್ನಡ",
            "tts_code": "kn",
            "gcp_code": "kn-IN",
        },
        "ml-IN": {
            "name": "Malayalam",
            "native": "മലയാളം",
            "tts_code": "ml",
            "gcp_code": "ml-IN",
        },
        "hi-IN": {
            "name": "Hindi",
            "native": "हिन्दी",
            "tts_code": "hi",
            "gcp_code": "hi-IN",
        }
    }

    @classmethod
    def is_in_quiet_hours(cls, priority: str = "NORMAL") -> bool:
        """
        Determines if current local time falls into quiet hours.
        CRITICAL priority bypasses quiet hours if configured.
        """
        if priority.upper() == "CRITICAL" and cls.EMERGENCY_OVERRIDE_QUIET_HOURS:
            return False

        now = datetime.now()
        current_hour = now.hour

        if cls.QUIET_HOURS_START > cls.QUIET_HOURS_END:
            # Over midnight (e.g. 21:00 to 06:00)
            return current_hour >= cls.QUIET_HOURS_START or current_hour < cls.QUIET_HOURS_END
        else:
            return cls.QUIET_HOURS_START <= current_hour < cls.QUIET_HOURS_END

settings = Settings()
