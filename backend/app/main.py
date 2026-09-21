"""FastAPI application entry point."""

import logging
import time
import uuid

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.limiter import limiter

from app.config import settings
from app.db.connection import get_pool, close_pool
from app.routers import parse, search, chat, analytics, investigate, alias_suggestions, insights, account, entity_timeline

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: open DB pool. Shutdown: close pool."""
    logger.info("Starting Silsila API — %s", settings.ENVIRONMENT)
    await get_pool()
    logger.info("Database pool ready")

    # Sentry init (Phase 6 — no-op if DSN is empty)
    if settings.SENTRY_DSN:
        import sentry_sdk
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            traces_sample_rate=0.2,
            environment=settings.ENVIRONMENT,
        )
        logger.info("Sentry initialized")

    yield

    await close_pool()
    logger.info("Database pool closed")


app = FastAPI(
    title="Silsila API",
    version="1.0.0",
    description="AI Memory Engine — relationship intelligence from your chats",
    lifespan=lifespan,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url=None,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

from fastapi.responses import JSONResponse

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> Response:
    logger.error("Unhandled exception for %s %s: %s", request.method, request.url.path, exc, exc_info=True)
    origin = request.headers.get("origin", "")
    headers = {}
    if origin in settings.allowed_origins_list or not settings.is_production:
        headers["Access-Control-Allow-Origin"] = origin or "*"
        headers["Access-Control-Allow-Credentials"] = "true"
        headers["Access-Control-Allow-Methods"] = "*"
        headers["Access-Control-Allow-Headers"] = "*"
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc) if not settings.is_production else "Internal Server Error"},
        headers=headers,
    )

# ── Middleware ────────────────────────────────────────────────────────────────

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next) -> Response:
    request_id = str(uuid.uuid4())[:8]
    start = time.perf_counter()
    response: Response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000)
    logger.info(
        "request",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    response.headers["X-Request-ID"] = request_id
    return response


# ── Routes ────────────────────────────────────────────────────────────────────

app.include_router(parse.router, prefix="/api", tags=["ingestion"])
app.include_router(search.router, prefix="/api", tags=["search"])
app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(analytics.router, prefix="/api", tags=["analytics"])
app.include_router(investigate.router, prefix="/api", tags=["investigate"])
app.include_router(alias_suggestions.router, prefix="/api", tags=["aliases"])
app.include_router(insights.router, prefix="/api", tags=["insights"])
app.include_router(account.router, prefix="/api", tags=["account"])
app.include_router(entity_timeline.router, prefix="/api", tags=["entities"])


@app.get("/api/health", tags=["ops"])
async def health_check():
    """UptimeRobot keep-alive + DB connectivity check."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.fetchval("SELECT 1")
    return {"status": "ok", "environment": settings.ENVIRONMENT}
