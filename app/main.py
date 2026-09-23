from fastapi import FastAPI

from app.api.routes.analysis import router as analysis_router
from app.api.routes.health import router as health_router
from app.api.routes.predictions import router as predictions_router
from app.config import get_settings

settings = get_settings()

app = FastAPI(title=settings.app_name, version="0.1.0")
app.include_router(health_router, prefix=settings.api_prefix)
app.include_router(predictions_router, prefix=settings.api_prefix)
app.include_router(analysis_router, prefix=settings.api_prefix)
