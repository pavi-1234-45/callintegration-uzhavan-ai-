from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import create_engine
from app.config import settings

# Async Engine and Session
async_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

# Sync Engine and Session for Celery / background synchronous tasks if needed
sync_engine = create_engine(
    settings.DATABASE_SYNC_URL,
    echo=False,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_SYNC_URL else {}
)

SyncSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=sync_engine
)

Base = declarative_base()

_db_initialized = False

async def ensure_db_initialized():
    global _db_initialized
    if not _db_initialized:
        await init_db()
        _db_initialized = True

async def get_db():
    """FastAPI dependency for database session"""
    await ensure_db_initialized()
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

def get_sync_db():
    """Synchronous database session generator for Celery tasks"""
    db = SyncSessionLocal()
    try:
        yield db
    finally:
        db.close()

async def init_db():
    """Initializes tables on startup and applies backward-compatible column migrations"""
    import app.models  # Ensure all models are registered on Base.metadata before create_all
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        def _migrate_columns(sync_conn):
            from sqlalchemy import text
            try:
                res = sync_conn.execute(text("PRAGMA table_info(farmers)")).fetchall()
                cols = [r[1] for r in res]
                if "source" not in cols:
                    sync_conn.execute(text("ALTER TABLE farmers ADD COLUMN source VARCHAR(50) DEFAULT 'survey_portal'"))
                    sync_conn.execute(text("UPDATE farmers SET source = 'mobile_app' WHERE farmer_id LIKE 'UZH-APP%'"))
            except Exception:
                pass

        await conn.run_sync(_migrate_columns)
