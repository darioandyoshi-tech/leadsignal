
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

def _is_local_postgres(url: str) -> bool:
    """Return True if the URL points to a local/dev Postgres instance."""
    host = urlparse(url).hostname or ""
    return host in ("localhost", "127.0.0.1", "::1") or host.endswith(".local")

# SQLite fallback for MVP demos / local dev when no Postgres is configured
if not settings.database_url_raw or "sqlite" in settings.database_url_raw:
    SQLITE_URL = settings.database_url
    SYNC_SQLITE_URL = settings.sync_database_url
    engine = create_async_engine(SQLITE_URL, echo=settings.debug)
    async_session_maker = async_sessionmaker(engine, expire_on_commit=False)
    sync_engine = create_engine(SYNC_SQLITE_URL, connect_args={"check_same_thread": False, "timeout": 60})
    sync_session_maker = sessionmaker(sync_engine)
else:
    # Managed Postgres (Render, Fly, etc.) requires TLS. Use a permissive SSL
    # context that works with both publicly-signed and self-signed certs.
    connect_args = {}
    database_url = settings.database_url
    sync_database_url = settings.sync_database_url

    if not _is_local_postgres(settings.database_url_raw):
        ctx = ssl_module.create_default_context()
        # Managed providers may use certs whose CN/SAN doesn't match the private
        # hostname; disabling verification avoids TLS handshake failures.
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
