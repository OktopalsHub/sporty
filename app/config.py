from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Sporty"
    app_env: str = "development"
    api_prefix: str = "/api/v1"
    sportybet_base_url: str = "https://www.sportybet.com"
    sportybet_region: str = "ng"
    sportybet_timeout: float = 15.0
    sportybet_min_interval: float = 0.25
    sportybet_max_retries: int = 3

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
