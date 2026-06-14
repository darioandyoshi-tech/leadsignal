
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import create_engine
from app.config import get_settings

settings = get_settings()

# Fly.io Postgres requires SSL; asyncpg needs it as connect_args
async_connect_args = {}
if settings.database_url_raw and ("flycast" in settings.database_url_raw or "sslmode" in settings.database_url_raw):
    async_connect_args["ssl"] = True

engine = create_async_engine(settings.database_url, echo=settings.debug, connect_args=async_connect_args)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)

sync_engine = create_engine(settings.sync_database_url)
sync_session_maker = sessionmaker(sync_engine)

Base = declarative_base()


async def get_db() -> AsyncSession:
    async with async_session_maker() as session:
        yield session
