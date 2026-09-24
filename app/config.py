from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_database_url(url: str) -> str:
    """Force the psycopg3 driver.

    A bare ``postgres://``/``postgresql://`` URL makes SQLAlchemy pick the
    psycopg2 dialect, and psycopg2 is not installed (only ``psycopg[binary]``).
    """
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url.removeprefix("postgresql://")
    return url


class Settings(BaseSettings):
    app_name: str = "Sporty"
    app_env: str = "development"
    api_prefix: str = "/api/v1"
    database_url: str = "postgresql+psycopg://sporty:sporty@localhost:5432/sporty"
    database_pool_size: int = 10
    database_max_overflow: int = 20
    database_pool_timeout: int = 30
    database_pool_recycle: int = 300
    database_connect_timeout: int = 10
    redis_url: str = "redis://localhost:6379/0"
    redis_timeout: float = 5.0
    redis_max_connections: int = 20
    redis_health_check_interval: int = 30
    rate_limit_requests: int = 120
    rate_limit_window_seconds: int = 60
    api_key: str | None = None
    docs_enabled: bool = True
    trusted_hosts: str = "localhost,127.0.0.1,testserver,*.fastapicloud.dev"
    security_headers_enabled: bool = True
    rate_limit_fail_closed: bool = True
    sportybet_provider: str = "parse"
    sportybet_base_url: str = "https://www.sportybet.com"
    sportybet_region: str = "ng"
    sportybet_timeout: float = 15.0
    sportybet_min_interval: float = 0.25
    sportybet_max_retries: int = 3
    parse_api_key: str | None = None
    parse_api_base_url: str = "https://api.parse.bot/scraper/8e652912-d760-4522-85ce-071e539a9c12"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    gemini_timeout: float = 30.0
    frontend_origins: str = "http://localhost:3000,http://localhost:5173"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    @field_validator("database_url", mode="after")
    @classmethod
    def _force_psycopg_driver(cls, value: str) -> str:
        return normalize_database_url(value)

    @field_validator("trusted_hosts", mode="after")
    @classmethod
    def _ensure_platform_host(cls, value: str) -> str:
        """Always allow the FastAPI Cloud platform domain.

        An env var (or stale .env) may set TRUSTED_HOSTS to a value that
        omits the deployment domain, which makes TrustedHostMiddleware
        reject every real request with 400 while the app still boots.
        """
        hosts = [host.strip() for host in value.split(",") if host.strip()]
        if "*.fastapicloud.dev" not in hosts:
            hosts.append("*.fastapicloud.dev")
        return ",".join(hosts)

    def validate_production(self) -> None:
        if self.app_env.lower() != "production":
            return
        if not self.api_key:
            raise ValueError("API_KEY must be configured when APP_ENV=production")
        if not self.trusted_host_list:
            raise ValueError("TRUSTED_HOSTS must contain at least one host in production")

    @property
    def frontend_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origins.split(",") if origin.strip()]

    @property
    def trusted_host_list(self) -> list[str]:
        return [host.strip() for host in self.trusted_hosts.split(",") if host.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
