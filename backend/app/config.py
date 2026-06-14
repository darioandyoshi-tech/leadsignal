from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "LeadSignal"
    debug: bool = False

    database_url_raw: str = Field(default="sqlite+aiosqlite:///./leadsignal.db", alias="DATABASE_URL")
    sync_database_url_raw: str = Field(default="sqlite:///./leadsignal.db", alias="SYNC_DATABASE_URL")

    @property
    def database_url(self) -> str:
        url = self.database_url_raw
        if not url or "sqlite" in url:
            return "sqlite+aiosqlite:///./leadsignal.db"
        if url.startswith("postgres://"):
            url = "postgresql" + url.removeprefix("postgres")
        if ".flycast:5432" in url:
            url = url.replace(":5432", ":5433")
        if "?" in url:
            base, query = url.split("?", 1)
            params = [p for p in query.split("&") if not p.startswith("sslmode")]
            url = base + ("?" + "&".join(params) if params else "")
        if "+asyncpg" not in url and "postgresql://" in url:
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    @property
    def sync_database_url(self) -> str:
        url = self.sync_database_url_raw
        if not url or "sqlite" in url:
            return "sqlite:///./leadsignal.db"
        if url.startswith("postgres://"):
            url = "postgresql" + url.removeprefix("postgres")
        if ".flycast:5432" in url:
            url = url.replace(":5432", ":5433")
        if "+psycopg2" not in url and "+asyncpg" not in url and "postgresql://" in url:
            url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
        return url

    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 1 week

    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_starter: str = ""
    stripe_price_pro: str = ""
    stripe_price_growth: str = ""

    frontend_url: str = "http://localhost:3000"

    google_places_api_key: str = ""
    yelp_api_key: str = ""

    agentmail_api_key: str = ""
    agentmail_sender: str = "alerts@leadsignal.ai"

    redis_url: str = "redis://localhost:6379/0"

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
