import logging
import re
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.api import api_router
from app.core.config import settings
from app.core.database import engine

logger = logging.getLogger(__name__)


def _safe_database_reason(original) -> str:
    reason = str(original or "")
    if engine.url.host and "@" in engine.url.host:
        reason = reason.replace(engine.url.host, "[invalid redacted host]")
    # Driver errors must never send connection credentials into runtime logs.
    secrets = [engine.url.password, settings.DATABASE_URL, settings.POSTGRES_PASSWORD,
               settings.SECRET_KEY, settings.SUPABASE_SERVICE_ROLE_KEY, settings.ADMIN_SETUP_TOKEN]
    for secret in sorted((value for value in secrets if value), key=len, reverse=True):
        reason = reason.replace(secret, "[redacted]")
    reason = re.sub(r"postgres(?:ql)?(?:\+psycopg)?://[^\s]+", "[redacted connection URL]", reason)
    return reason[:1500]

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Unified DestinLane Allied Services ERP API.",
    openapi_url=f"{settings.API_V1_STR}/openapi.json" if settings.DEBUG else None,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)


@app.exception_handler(SQLAlchemyError)
async def database_error(request: Request, exc: SQLAlchemyError):
    """Report database failures without returning connection strings or SQL."""
    error_id = uuid4().hex
    original = getattr(exc, "orig", None)
    sqlstate = getattr(original, "sqlstate", None)
    message = str(original or "").lower()
    if sqlstate and sqlstate.startswith("28"):
        code = "DATABASE_CREDENTIALS_INVALID"
    elif sqlstate in {"42P01", "42703"}:
        code = "DATABASE_SCHEMA_MISMATCH"
    elif "network is unreachable" in message:
        code = "DATABASE_NETWORK_UNREACHABLE"
    elif "could not translate host name" in message or "name or service not known" in message:
        code = "DATABASE_HOST_UNRESOLVED"
    elif "connection refused" in message:
        code = "DATABASE_CONNECTION_REFUSED"
    elif "tenant or user not found" in message:
        code = "DATABASE_POOLER_IDENTITY_INVALID"
    elif "password authentication failed" in message:
        code = "DATABASE_CREDENTIALS_INVALID"
    elif "timeout expired" in message or "connection timed out" in message:
        code = "DATABASE_CONNECTION_TIMEOUT"
    else:
        code = "DATABASE_UNAVAILABLE"
    logger.error("Database request failed: error_id=%s code=%s exception=%s sqlstate=%s path=%s host=%s port=%s configured=%s reason=%s",
                 error_id, code, type(exc).__name__, sqlstate, request.url.path,
                 "[invalid redacted host]" if engine.url.host and "@" in engine.url.host else engine.url.host,
                 engine.url.port, bool(settings.DATABASE_URL), _safe_database_reason(original))
    return JSONResponse(status_code=503, content={
        "detail": "The ERP database is unavailable. Please contact the administrator.",
        "error_code": code,
        "error_id": error_id,
    })

if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept"],
    )


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(self), geolocation=(self), microphone=()"
    if not settings.DEBUG:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "healthy",
        "app": settings.PROJECT_NAME,
        "version": settings.VERSION,
    }


app.include_router(api_router, prefix=settings.API_V1_STR)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=settings.DEBUG)
