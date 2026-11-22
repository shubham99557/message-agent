import logging
import uuid
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.crypto import decrypt_secret
from app.core.database import engine, SessionLocal, sync_missing_columns
from app.core.logging_config import configure_structured_logging, request_id_ctx, redact_sensitive_text
import app.models  # noqa: F401 - ensure all ORM models are registered on Base.metadata
from app.api.api_v1 import api_router
from app.services.auth_service import seed_default_admin
from app.services.whatsapp_service import seed_default_meta_templates

configure_structured_logging()
logger = logging.getLogger("acttrident.api")


def apply_saved_integrations(db):
    """Hydrates runtime settings from encrypted IntegrationCredential rows strictly in memory."""
    from app.models.activity import IntegrationCredential
    from app.services.ai_provider import ai_service

    creds = db.query(IntegrationCredential).filter(IntegrationCredential.is_active == True).all()
    for cred in creds:
        plain_secret = decrypt_secret(cred.encrypted_value) if cred.encrypted_value else None
        if cred.provider == "gemini" and plain_secret:
            settings.AI_PROVIDER = "gemini"
            settings.GEMINI_API_KEY = plain_secret
            ai_service.provider = "gemini"
            ai_service.gemini_key = plain_secret
        elif cred.provider == "openai" and plain_secret:
            settings.AI_PROVIDER = "openai"
            settings.OPENAI_API_KEY = plain_secret
            ai_service.provider = "openai"
            ai_service.openai_key = plain_secret
        elif cred.provider == "smtp" and plain_secret:
            settings.EMAIL_PROVIDER = "smtp"
            if cred.key_identifier:
                settings.SMTP_USER = cred.key_identifier
                settings.SMTP_FROM_EMAIL = cred.key_identifier
            settings.SMTP_PASSWORD = plain_secret
        elif cred.provider == "whatsapp_meta" and plain_secret:
            settings.META_WA_ACCESS_TOKEN = plain_secret
            if cred.key_identifier:
                settings.META_WA_PHONE_NUMBER_ID = cred.key_identifier


class RequestCorrelationMiddleware(BaseHTTPMiddleware):
    """Attaches a unique X-Request-ID correlation identifier to every request and log line."""

    async def dispatch(self, request: Request, call_next):
        incoming_id = request.headers.get("X-Request-ID")
        req_id = incoming_id[:64] if incoming_id else str(uuid.uuid4())
        token = request_id_ctx.set(req_id)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = req_id
            return response
        finally:
            request_id_ctx.reset(token)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Enforce production/staging security constraints at startup
    settings.validate_production_security()

    # Ensure local %LOCALAPPDATA%\ActTrident storage layout is initialized
    from app.core.storage import initialize_storage_layout
    initialize_storage_layout()

    # In production, schema changes must be applied explicitly via Alembic (`alembic upgrade head`).
    # Automatic schema sync is restricted to non-production environments only.
    if settings.ENVIRONMENT.lower() in ("development", "test"):
        sync_missing_columns(engine)

    db = SessionLocal()
    try:
        from app.services.job_service import recover_dangling_tasks
        recover_dangling_tasks(db)
        if settings.ENVIRONMENT.lower() != "production":
            seed_default_admin(db)
        seed_default_meta_templates(db)
        apply_saved_integrations(db)

        # Start persistent local background scheduler
        from app.services.local_scheduler import local_scheduler
        local_scheduler.start()
    except Exception as exc:
        logger.warning(f"Startup bootstrap notice: {redact_sensitive_text(str(exc))}")
    finally:
        db.close()

    logger.info(f"ActTrident API started (environment={settings.ENVIRONMENT})")
    yield

    # Clean shutdown of local scheduler thread
    try:
        from app.services.local_scheduler import local_scheduler
        local_scheduler.stop()
    except Exception:
        pass


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# Correlation ID Middleware
app.add_middleware(RequestCorrelationMiddleware)

# CORS Middleware: Explicit non-wildcard origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)


# Consistent Structured API Error Handlers (no secret or stack trace leakage)
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    req_id = request_id_ctx.get("-")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "http_error",
            "detail": exc.detail,
            "request_id": req_id,
        },
        headers={"X-Request-ID": req_id, **(exc.headers or {})},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    req_id = request_id_ctx.get("-")
    safe_errors = []
    for err in exc.errors():
        safe_errors.append({
            "loc": err.get("loc"),
            "msg": err.get("msg"),
            "type": err.get("type"),
        })
    return JSONResponse(
        status_code=422,
        content={
            "error": "validation_error",
            "detail": safe_errors,
            "request_id": req_id,
        },
        headers={"X-Request-ID": req_id},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    req_id = request_id_ctx.get("-")
    logger.error(f"Unhandled exception on {request.method} {request.url.path}: {redact_sensitive_text(str(exc))}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "detail": "An unexpected internal error occurred. Reference the request_id for support.",
            "request_id": req_id,
        },
        headers={"X-Request-ID": req_id},
    )


app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/health")
def health_check():
    """Liveness probe."""
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
        "version": "2.1.0"
    }


@app.get("/ready")
def readiness_check():
    """Readiness probe verifying live database connectivity and startup security compliance."""
    db_ok = False
    db_error = None
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception as exc:
        db_error = redact_sensitive_text(str(exc))
    finally:
        db.close()

    if not db_ok:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "database": "unavailable",
                "detail": db_error,
                "request_id": request_id_ctx.get("-")
            }
        )

    return {
        "status": "ready",
        "database": "connected",
        "environment": settings.ENVIRONMENT,
        "request_id": request_id_ctx.get("-")
    }


# Mount Built React Frontend Distribution for Unified Windows Desktop Serving
_frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if _frontend_dist.exists():
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse

    _assets_dir = _frontend_dist / "assets"
    if _assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(_assets_dir)), name="frontend_assets")

    @app.get("/{full_path:path}")
    async def serve_spa_frontend(full_path: str):
        file_candidate = _frontend_dist / full_path
        if full_path and file_candidate.is_file():
            return FileResponse(file_candidate)
        index_file = _frontend_dist / "index.html"
        if index_file.is_file():
            return FileResponse(index_file)
        raise HTTPException(status_code=404, detail="Frontend asset not found")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
