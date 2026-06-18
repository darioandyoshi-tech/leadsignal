from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache
import os
from pathlib import Path


class Settings(BaseSettings):
    app_name: str = "LeadSignal"
    debug: bool = False

    database_url_raw: str = Field(default="sqlite+aiosqlite:///./leadsignal.db", alias="DATABASE_URL")
    sync_database_url_raw: str = Field(default="sqlite:///./leadsignal.db", alias="SYNC_DATABASE_URL")

    @property
    def database_url(self) -> str:
        url = self.database_url_raw
        if not url or "sqlite" in url:
            # Use an absolute path so async app and sync scrapers share the same file.
            return f"sqlite+aiosqlite:///{self._db_path()}"
        if url.startswith("postgres://"):
            url = "postgresql" + url.removeprefix("postgres")
        if ".flycast:5432" in url:
            url = url.replace(":5432", ":5433")
            # Fly Postgres uses a self-signed cert over the internal network;
            # disable SSL verification and strip sslmode params.
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
            return f"sqlite:///{self._db_path()}"
        if url.startswith("postgres://"):
            url = "postgresql" + url.removeprefix("postgres")
        if ".flycast:5432" in url:
            url = url.replace(":5432", ":5433")
            if "?" in url:
                base, query = url.split("?", 1)
                params = [p for p in query.split("&") if not p.startswith("sslmode")]
                url = base + ("?" + "&".join(params) if params else "")
        if "+psycopg2" not in url and "+asyncpg" not in url and "postgresql://" in url:
            url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
        return url

    @staticmethod
    def _db_path() -> str:
        # Render and local dev both use /opt/render/project/src/backend on Render,
        # or the backend directory when running locally. Put the SQLite file there.
        cwd = os.getcwd()
        # If we're inside the backend dir, use cwd. Otherwise resolve to backend/.
        if os.path.basename(cwd) == "backend":
            return os.path.abspath("leadsignal.db")
        backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        return os.path.join(backend_dir, "leadsignal.db")

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

    timesfm_url: str = ""
    timesfm_api_key_file: str = ".env.timesfm"

    @property
    def timesfm_api_key(self) -> str:
        try:
            path = self.timesfm_api_key_file if os.path.isabs(self.timesfm_api_key_file) else os.path.join(os.path.dirname(__file__), "..", self.timesfm_api_key_file)
            return Path(path).resolve().read_text().strip().split("=", 1)[1].strip().strip('"\'')
        except Exception:
            return os.environ.get("TIMESFM_API_KEY", "")

    # Alpaca paper/live trading
    alpaca_base_url: str = "https://paper-api.alpaca.markets/v2"
    alpaca_api_key: str = ""
    alpaca_secret_key: str = ""
    alpaca_paper: bool = True
    alpaca_auto_trade: bool = False
    alpaca_max_open_positions: int = 5
    alpaca_capital_per_trade: float = 2000.0
    alpaca_max_hold_days: int = 4
    alpaca_daily_max_loss: float = 500.0
    alpaca_max_portfolio_heat: float = 0.5  # max 50% of cash deployed at once

    class Config:
        env_file = ".env"
        extra = "ignore"  # tolerate extra env vars in .env


@lru_cache()
def get_settings() -> Settings:
    return Settings()
