from functools import lru_cache

import logfire

from app.config import get_settings


@lru_cache
def configure_logfire() -> None:
    settings = get_settings()
    logfire.configure(
        send_to_logfire="if-token-present",
        service_name=settings.app_name,
        service_version="0.1.0",
        environment=settings.app_env,
    )
