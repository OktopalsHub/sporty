import secrets

import logfire
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from app.api.routes.analysis import router as analysis_router
from app.api.routes.five_k import router as five_k_router
from app.api.routes.generators import router as generators_router
from app.api.routes.health import router as health_router
from app.api.routes.history import router as history_router
from app.api.routes.jobs import router as jobs_router
from app.api.routes.meta import router as meta_router
from app.api.routes.one_k import router as one_k_router
from app.api.routes.predictions import router as predictions_router
from app.api.routes.selections import router as selections_router
from app.api.routes.tickets import router as tickets_router
from app.api.routes.weekly_safe import router as weekly_safe_router
from app.cache import get_redis
from app.config import get_settings
from app.db import engine
from app.rate_limit import RedisRateLimiter
from app.observability import configure_logfire

settings = get_settings()
settings.validate_production()

configure_logfire()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url="/redoc" if settings.docs_enabled else None,
    openapi_url="/openapi.json" if settings.docs_enabled else None,
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.trusted_host_list,
)
logfire.instrument_fastapi(app)
logfire.instrument_sqlalchemy(engine=engine)
logfire.instrument_httpx()
logfire.instrument_redis()

rate_limiter = RedisRateLimiter(
    get_redis(),
    limit=settings.rate_limit_requests,
    window_seconds=settings.rate_limit_window_seconds,
)

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

    require_api_key = settings.app_env.lower() == "production" or bool(settings.api_key)
    if require_api_key and request.url.path.startswith(settings.api_prefix):
        if request.url.path not in {
            f"{settings.api_prefix}/health",
            f"{settings.api_prefix}/ready",
        }:
            supplied_key = request.headers.get("X-API-Key", "")
            if not secrets.compare_digest(supplied_key, settings.api_key):
                response = JSONResponse(
                    status_code=401,
                    content={
                        "error": {
                            "code": "invalid_api_key",
                            "message": "A valid API key is required",
                        },
                        "request_id": request_id,
                    },
                )
                response.headers["X-Request-ID"] = request_id
                return response

    if request.url.path.startswith(settings.api_prefix) and request.url.path not in {
        f"{settings.api_prefix}/health",
        f"{settings.api_prefix}/ready",
    }:
        client_id = request.headers.get("X-API-Key") or (
            request.client.host if request.client else "unknown"
        )
        try:
            result = await rate_limiter.check(client_id)
            if not result.allowed:
                response = JSONResponse(
                    status_code=429,
                    content={
                        "error": {
                            "code": "rate_limit_exceeded",
                            "message": "Too many requests",
                        },
                        "request_id": request_id,
                    },
                )
                response.headers["X-Request-ID"] = request_id
                response.headers["X-RateLimit-Limit"] = str(result.limit)
                response.headers["X-RateLimit-Remaining"] = str(result.remaining)
                response.headers["Retry-After"] = str(result.retry_after)
                return response
        except Exception:
            if settings.rate_limit_fail_closed:
                response = JSONResponse(
                    status_code=503,
                    content={
                        "error": {
                            "code": "rate_limit_unavailable",
                            "message": "Request protection is temporarily unavailable",
                        },
                        "request_id": request_id,
                    },
                )
                response.headers["X-Request-ID"] = request_id
                return response

    try:
        response = await call_next(request)
    except Exception:
        response = JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_server_error",
                    "message": "Internal server error",
                },
                "request_id": request_id,
            },
        )

    response.headers["X-Request-ID"] = request_id
    return response


@app.on_event("shutdown")
async def shutdown() -> None:
    from app.cache import close_redis

    await close_redis()


app.include_router(health_router, prefix=settings.api_prefix)
app.include_router(predictions_router, prefix=settings.api_prefix)
app.include_router(selections_router, prefix=settings.api_prefix)
app.include_router(tickets_router, prefix=settings.api_prefix)
app.include_router(history_router, prefix=settings.api_prefix)
app.include_router(jobs_router, prefix=settings.api_prefix)
app.include_router(meta_router, prefix=settings.api_prefix)
app.include_router(analysis_router, prefix=settings.api_prefix)
app.include_router(generators_router, prefix=settings.api_prefix)
app.include_router(one_k_router, prefix=settings.api_prefix)
app.include_router(five_k_router, prefix=settings.api_prefix)
app.include_router(weekly_safe_router, prefix=settings.api_prefix)
