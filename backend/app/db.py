
import ssl as ssl_module
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import create_engine
from app.config import get_settings

settings = get_settings()


def _strip_sslmode(url: str) -> str:
    """Remove sslmode query param from a URL so asyncpg doesn't receive it."""
    parsed = urlparse(url)
    if not parsed.query:
        return url
    params = [(k, v) for k, v in parse_qsl(parsed.query) if k != "sslmode"]
    query = urlencode(params)
    return urlunparse(parsed._replace(query=query))

# SQLite fallback for MVP demos / local dev when no Postgres is configured
if not settings.database_url_raw or "sqlite" in settings.database_url_raw:
    SQLITE_URL = settings.database_url
    SYNC_SQLITE_URL = settings.sync_database_url
    engine = create_async_engine(SQLITE_URL, echo=settings.debug)
    async_session_maker = async_sessionmaker(engine, expire_on_commit=False)
    sync_engine = create_engine(SYNC_SQLITE_URL, connect_args={"check_same_thread": False, "timeout": 60})
    sync_session_maker = sessionmaker(sync_engine)
else:
    # External Postgres (Render, Fly) requires TLS. Render's cert is signed by a
    # public CA, so we can use the default context. Fly uses a self-signed cert
    # over the internal network, so we disable verification for flycast hosts.
    connect_args = {}
    database_url = settings.database_url
    sync_database_url = settings.sync_database_url

    requires_ssl = (
        "flycast" in settings.database_url_raw
        or ".render.com" in settings.database_url_raw
        or "sslmode" in settings.database_url_raw
    )
    if requires_ssl:
        ctx = ssl_module.create_default_context()
        if "flycast" in settings.database_url_raw:
            ctx.check_hostname = False
            ctx.verify_mode = ssl_module.CERT_NONE
        connect_args["ssl"] = ctx
        # asyncpg does not accept the sslmode keyword, so strip it from the async URL.
        database_url = _strip_sslmode(database_url)
        # Ensure the sync URL still requests SSL (psycopg2 understands sslmode).
        if "sslmode" not in sync_database_url:
            sync_database_url += "?sslmode=require" if "?" not in sync_database_url else "&sslmode=require"

    engine = create_async_engine(database_url, echo=settings.debug, connect_args=connect_args)
    async_session_maker = async_sessionmaker(engine, expire_on_commit=False)
    sync_engine = create_engine(sync_database_url)
    sync_session_maker = sessionmaker(sync_engine)

Base = declarative_base()


async def get_db() -> AsyncSession:
    async with async_session_maker() as session:
        yield session
