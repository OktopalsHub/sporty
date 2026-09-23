from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from uuid import uuid4

from app.api.routes.analysis import router as analysis_router
from app.api.routes.five_k import router as five_k_router
from app.api.routes.generators import router as generators_router
from app.api.routes.health import router as health_router
from app.api.routes.history import router as history_router
from app.api.routes.meta import router as meta_router
from app.api.routes.one_k import router as one_k_router
from app.api.routes.predictions import router as predictions_router
from app.api.routes.selections import router as selections_router
from app.api.routes.tickets import router as tickets_router
from app.api.routes.weekly_safe import router as weekly_safe_router
from app.config import get_settings

settings = get_settings()

app = FastAPI(title=settings.app_name, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    try:
        response = await call_next(request)
    except Exception:
        response = JSONResponse(
            status_code=500,
            content={"error": {"code": "internal_server_error", "message": "Internal server error"}, "request_id": request_id},
        )
    response.headers["X-Request-ID"] = request_id
    return response


app.include_router(health_router, prefix=settings.api_prefix)
app.include_router(predictions_router, prefix=settings.api_prefix)
app.include_router(selections_router, prefix=settings.api_prefix)
app.include_router(tickets_router, prefix=settings.api_prefix)
app.include_router(history_router, prefix=settings.api_prefix)
app.include_router(meta_router, prefix=settings.api_prefix)
app.include_router(analysis_router, prefix=settings.api_prefix)
app.include_router(generators_router, prefix=settings.api_prefix)
app.include_router(one_k_router, prefix=settings.api_prefix)
app.include_router(five_k_router, prefix=settings.api_prefix)
app.include_router(weekly_safe_router, prefix=settings.api_prefix)
