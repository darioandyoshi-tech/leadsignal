
import ssl as ssl_module
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import create_engine
from app.config import get_settings

settings = get_settings()

# SQLite fallback for MVP demos / local dev when no Postgres is configured
if not settings.database_url_raw or "sqlite" in settings.database_url_raw:
    SQLITE_URL = "sqlite+aiosqlite:///./leadsignal.db"
    SYNC_SQLITE_URL = "sqlite:///./leadsignal.db"
    engine = create_async_engine(SQLITE_URL, echo=settings.debug)
    async_session_maker = async_sessionmaker(engine, expire_on_commit=False)
    sync_engine = create_engine(SYNC_SQLITE_URL)
    sync_session_maker = sessionmaker(sync_engine)
else:
    # Fly Postgres uses a self-signed cert over the internal network; disable verification
    connect_args = {}
    if "flycast" in settings.database_url_raw or "sslmode" in settings.database_url_raw:
        ctx = ssl_module.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl_module.CERT_NONE
        connect_args["ssl"] = ctx

    engine = create_async_engine(settings.database_url, echo=settings.debug, connect_args=connect_args)
    async_session_maker = async_sessionmaker(engine, expire_on_commit=False)
    sync_engine = create_engine(settings.sync_database_url)
    sync_session_maker = sessionmaker(sync_engine)

Base = declarative_base()


async def get_db() -> AsyncSession:
    async with async_session_maker() as session:
        yield session
