from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import engine, Base, SessionLocal, sync_missing_columns
import app.models  # noqa: F401 - ensure all ORM models are registered on Base.metadata
from app.api.api_v1 import api_router
from app.services.auth_service import seed_default_admin
from app.services.whatsapp_service import seed_default_meta_templates


def apply_saved_integrations(db):
    """Hydrates runtime settings from saved IntegrationCredential rows."""
    from app.models.activity import IntegrationCredential
    from app.services.ai_provider import ai_service

    creds = db.query(IntegrationCredential).filter(IntegrationCredential.is_active == True).all()
    for cred in creds:
        if cred.provider == "gemini" and cred.encrypted_value:
            settings.AI_PROVIDER = "gemini"
            settings.GEMINI_API_KEY = cred.encrypted_value
            ai_service.provider = "gemini"
            ai_service.gemini_key = cred.encrypted_value
        elif cred.provider == "openai" and cred.encrypted_value:
            settings.AI_PROVIDER = "openai"
            settings.OPENAI_API_KEY = cred.encrypted_value
            ai_service.provider = "openai"
            ai_service.openai_key = cred.encrypted_value
        elif cred.provider == "smtp" and cred.encrypted_value:
            settings.EMAIL_PROVIDER = "smtp"
            if cred.key_identifier:
                settings.SMTP_USER = cred.key_identifier
                settings.SMTP_FROM_EMAIL = cred.key_identifier
            settings.SMTP_PASSWORD = cred.encrypted_value
        elif cred.provider == "whatsapp_meta" and cred.encrypted_value:
            settings.META_WA_ACCESS_TOKEN = cred.encrypted_value
            if cred.key_identifier:
                settings.META_WA_PHONE_NUMBER_ID = cred.key_identifier


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Enforce production security constraints
    settings.validate_production_security()

    # Ensure all tables and newly added columns exist on startup
    sync_missing_columns(engine)
    
    # Bootstrap initial admin if provided via environment, seed WA templates, hydrate integrations
    db = SessionLocal()
    try:
        seed_default_admin(db)
        seed_default_meta_templates(db)
        apply_saved_integrations(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# CORS Middleware: Explicit non-wildcard origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
        "version": "2.0.0"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
