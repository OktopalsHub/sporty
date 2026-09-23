from fastapi import FastAPI

from app.api.routes.analysis import router as analysis_router
from app.api.routes.five_k import router as five_k_router
from app.api.routes.generators import router as generators_router
from app.api.routes.health import router as health_router
from app.api.routes.history import router as history_router
from app.api.routes.one_k import router as one_k_router
from app.api.routes.predictions import router as predictions_router
from app.api.routes.selections import router as selections_router
from app.api.routes.tickets import router as tickets_router
from app.api.routes.weekly_safe import router as weekly_safe_router
from app.config import get_settings
from app.db import init_db

settings = get_settings()
init_db()

app = FastAPI(title=settings.app_name, version="0.1.0")
app.include_router(health_router, prefix=settings.api_prefix)
app.include_router(predictions_router, prefix=settings.api_prefix)
app.include_router(selections_router, prefix=settings.api_prefix)
app.include_router(tickets_router, prefix=settings.api_prefix)
app.include_router(history_router, prefix=settings.api_prefix)
app.include_router(analysis_router, prefix=settings.api_prefix)
app.include_router(generators_router, prefix=settings.api_prefix)
app.include_router(one_k_router, prefix=settings.api_prefix)
app.include_router(five_k_router, prefix=settings.api_prefix)
app.include_router(weekly_safe_router, prefix=settings.api_prefix)
