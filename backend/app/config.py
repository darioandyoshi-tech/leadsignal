
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "LeadSignal"
    debug: bool = False

    database_url: str = "postgresql+asyncpg://leadsignal:leadsignal@localhost:5432/leadsignal"
    sync_database_url: str = "postgresql://leadsignal:leadsignal@localhost:5432/leadsignal"

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
