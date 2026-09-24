from functools import lru_cache
import os

import logfire

from app.config import get_settings


@lru_cache
def configure_logfire() -> None:
    settings = get_settings()
    send_to_logfire = os.getenv("LOGFIRE_SEND_TO_LOGFIRE", "if-token-present")
    if send_to_logfire.lower() in {"true", "1", "yes"}:
        send_to_logfire = True
    elif send_to_logfire.lower() in {"false", "0", "no"}:
        send_to_logfire = False

    logfire.configure(
        send_to_logfire=send_to_logfire,
        service_name=os.getenv("LOGFIRE_SERVICE_NAME", settings.app_name),
        service_version=os.getenv("LOGFIRE_SERVICE_VERSION", "0.1.0"),
        environment=os.getenv("LOGFIRE_ENVIRONMENT", settings.app_env),
    )
