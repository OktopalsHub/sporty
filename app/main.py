from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.config import get_settings

settings = get_settings()

app = FastAPI(title=settings.app_name, version="0.1.0")
app.include_router(health_router, prefix=settings.api_prefix)
